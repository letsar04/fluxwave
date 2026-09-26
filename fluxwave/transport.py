from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse


@dataclass(frozen=True)
class PeerEndpoint:
    peer_id: str
    base_url: str


@dataclass
class PeerStats:
    peer_id: str
    successes: int = 0
    failures: int = 0
    bytes_received: int = 0
    elapsed_seconds: float = 0.0

    @property
    def throughput_mbps(self) -> float:
        if self.elapsed_seconds <= 0:
            return 0.0
        return self.bytes_received * 8 / self.elapsed_seconds / 1_000_000


class CongestionController:
    """AIMD controller for per-peer application-level concurrency."""

    def __init__(self, initial_window: int = 2, max_window: int = 8) -> None:
        if initial_window <= 0 or max_window < initial_window:
            raise ValueError("invalid congestion window")
        self.window = initial_window
        self.max_window = max_window
        self._lock = threading.Lock()

    def success(self) -> int:
        with self._lock:
            self.window = min(self.max_window, self.window + 1)
            return self.window

    def failure(self) -> int:
        with self._lock:
            self.window = max(1, self.window // 2)
            return self.window


class PersistentPeerClient:
    """HTTP/1.1 client retaining one connection per worker thread."""

    def __init__(self, base_url: str, *, timeout: float = 60.0, verify_tls: bool = True) -> None:
        parsed = urlparse(base_url.rstrip("/"))
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("peer URL must use http:// or https://")
        self.base_url = base_url.rstrip("/")
        self.parsed = parsed
        self.timeout = timeout
        self.verify_tls = verify_tls
        self._local = threading.local()

    def _connection(self):
        connection = getattr(self._local, "connection", None)
        if connection is not None:
            return connection
        if self.parsed.scheme == "https":
            context = ssl.create_default_context()
            if not self.verify_tls:
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
            connection = http.client.HTTPSConnection(
                self.parsed.hostname, self.parsed.port,
                timeout=self.timeout, context=context,
            )
        else:
            connection = http.client.HTTPConnection(
                self.parsed.hostname, self.parsed.port, timeout=self.timeout
            )
        self._local.connection = connection
        return connection

    def _request(self, path: str):
        connection = self._connection()
        try:
            connection.request("GET", path, headers={"Connection": "keep-alive"})
            response = connection.getresponse()
            if response.status >= 400:
                response.read()
                raise ConnectionError(f"peer returned HTTP {response.status}")
            return response
        except Exception:
            connection.close()
            self._local.connection = None
            raise

    def get_json(self, path: str) -> dict[str, object]:
        response = self._request(path)
        try:
            return json.loads(response.read().decode("utf-8"))
        finally:
            response.close()

    def download_chunk(self, index: int, expected_digest: str, destination: Path) -> int:
        response = self._request(f"/chunk/{index:06d}.chunk")
        temporary = destination.with_name(f".{destination.name}.part")
        digest = hashlib.sha256()
        received = 0
        try:
            with temporary.open("wb") as handle:
                while True:
                    block = response.read(1024 * 1024)
                    if not block:
                        break
                    handle.write(block)
                    digest.update(block)
                    received += len(block)
            if digest.hexdigest() != expected_digest:
                temporary.unlink(missing_ok=True)
                raise ValueError(f"checksum mismatch for chunk {index}")
            temporary.replace(destination)
            return received
        finally:
            response.close()


    """Minimal HTTP peer for verified chunk transfer.

    Designed for LAN experiments. HTTPS should be placed in front of this
    transport for untrusted networks.
    """

    def __init__(self, chunks_dir: str | Path, host: str = "0.0.0.0", port: int = 8765):
        self.chunks_dir = Path(chunks_dir)
        self.host = host
        self.port = port

    def serve_forever(self) -> None:
        directory = self.chunks_dir

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                parsed = urlparse(self.path)
                if parsed.path == "/manifest.json":
                    self._send_file(directory / "manifest.json", "application/json")
                    return

                if parsed.path.startswith("/chunk/") and parsed.path.endswith(".chunk"):
                    name = parsed.path.rsplit("/", 1)[-1]
                    if not name[:-6].isdigit():
                        self.send_error(404)
                        return
                    self._send_file(directory / name, "application/octet-stream")
                    return

                self.send_error(404)

            def _send_file(self, path: Path, content_type: str) -> None:
                if not path.is_file():
                    self.send_error(404)
                    return
                payload = path.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, format: str, *args: object) -> None:
                return

        server = ThreadingHTTPServer((self.host, self.port), Handler)
        print(f"FluxWave peer listening on http://{self.host}:{self.port}")
        server.serve_forever()


def _verify_existing(path: Path, expected_digest: str) -> bool:
    if not path.is_file():
        return False
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest() == expected_digest


def download_from_peers(
    peers: list[PeerEndpoint],
    output_dir: str | Path,
    *,
    workers_per_peer: int = 2,
    max_retries: int = 3,
    timeout: float = 60.0,
    verify_tls: bool = True,
) -> dict[str, PeerStats]:
    if not peers:
        raise ValueError("at least one peer is required")
    if workers_per_peer <= 0 or max_retries <= 0:
        raise ValueError("workers_per_peer and max_retries must be positive")

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    normalized = list({peer.peer_id: peer for peer in peers}.values())

    manifest = None
    for peer in normalized:
        try:
            manifest = PersistentPeerClient(peer.base_url, timeout=timeout, verify_tls=verify_tls).get_json("/manifest.json")
            break
        except Exception:
            continue
    if manifest is None:
        raise ConnectionError("no peer could provide a manifest")

    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    expected = [str(item) for item in manifest["chunks"]]
    jobs = [(i, digest) for i, digest in enumerate(expected) if not _verify_existing(output / f"{i:06d}.chunk", digest)]

    stats = {peer.peer_id: PeerStats(peer.peer_id) for peer in normalized}
    controllers = {peer.peer_id: CongestionController(min(2, workers_per_peer), workers_per_peer) for peer in normalized}
    clients = {peer.peer_id: PersistentPeerClient(peer.base_url, timeout=timeout, verify_tls=verify_tls) for peer in normalized}

    def fetch(job: tuple[int, str]) -> None:
        index, digest = job
        tried: set[str] = set()
        last_error: Exception | None = None
        for _ in range(max_retries):
            choices = [p for p in normalized if p.peer_id not in tried] or normalized
            peer = min(choices, key=lambda p: (stats[p.peer_id].failures, -stats[p.peer_id].throughput_mbps))
            tried.add(peer.peer_id)
            started = time.monotonic()
            try:
                received = clients[peer.peer_id].download_chunk(index, digest, output / f"{index:06d}.chunk")
                elapsed = max(time.monotonic() - started, 1e-9)
                stats[peer.peer_id].successes += 1
                stats[peer.peer_id].bytes_received += received
                stats[peer.peer_id].elapsed_seconds += elapsed
                controllers[peer.peer_id].success()
                return
            except Exception as exc:
                last_error = exc
                stats[peer.peer_id].failures += 1
                controllers[peer.peer_id].failure()
        raise RuntimeError(f"chunk {index} failed after {max_retries} attempts") from last_error

    with ThreadPoolExecutor(max_workers=max(1, len(normalized) * workers_per_peer)) as pool:
        futures = [pool.submit(fetch, job) for job in jobs]
        for future in as_completed(futures):
            future.result()

    return stats


def download_from_peer(base_url: str, output_dir: str | Path, *, workers: int = 4) -> Path:
    download_from_peers([PeerEndpoint("peer-0", base_url)], output_dir, workers_per_peer=workers)
    return Path(output_dir) / "manifest.json"

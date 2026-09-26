from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import hashlib
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hmac
import json
from pathlib import Path
import ssl
import threading
import time
from urllib.parse import urlparse


MAX_MANIFEST_CHUNKS = 1_000_000
MAX_PEER_ID_LENGTH = 128


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
        self.active = 0
        self._condition = threading.Condition()

    def acquire(self) -> None:
        with self._condition:
            while self.active >= self.window:
                self._condition.wait()
            self.active += 1

    def success(self) -> int:
        with self._condition:
            self.active -= 1
            self.window = min(self.max_window, self.window + 1)
            self._condition.notify_all()
            return self.window

    def failure(self) -> int:
        with self._condition:
            self.active -= 1
            self.window = max(1, self.window // 2)
            self._condition.notify_all()
            return self.window


class PersistentPeerClient:
    """HTTP/1.1 client retaining one connection per worker thread."""

    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = 60.0,
        verify_tls: bool = True,
        auth_token: str | None = None,
    ) -> None:
        parsed = urlparse(base_url.rstrip("/"))
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("peer URL must use http:// or https://")
        if parsed.username or parsed.password:
            raise ValueError("credentials in peer URLs are not allowed")
        self.base_url = base_url.rstrip("/")
        self.parsed = parsed
        self.timeout = timeout
        self.verify_tls = verify_tls
        self.auth_token = auth_token
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
                self.parsed.hostname,
                self.parsed.port,
                timeout=self.timeout,
                context=context,
            )
        else:
            connection = http.client.HTTPConnection(
                self.parsed.hostname,
                self.parsed.port,
                timeout=self.timeout,
            )
        self._local.connection = connection
        return connection

    def _request(self, path: str):
        if not path.startswith("/") or ".." in path.split("/"):
            raise ValueError("invalid peer path")
        connection = self._connection()
        headers = {"Connection": "keep-alive"}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        try:
            connection.request("GET", path, headers=headers)
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


class FluxWaveHTTPServer:
    """HTTP/1.1 peer with optional TLS and bearer-token authentication."""

    def __init__(
        self,
        chunks_dir: str | Path,
        host: str = "127.0.0.1",
        port: int = 8765,
        *,
        peer_id: str = "fluxwave-peer",
        certfile: str | Path | None = None,
        keyfile: str | Path | None = None,
        auth_token: str | None = None,
        max_connections: int = 32,
    ) -> None:
        self.chunks_dir = Path(chunks_dir).resolve()
        self.host = host
        self.port = port
        self.peer_id = peer_id
        self.certfile = str(certfile) if certfile else None
        self.keyfile = str(keyfile) if keyfile else None
        self.auth_token = auth_token
        self.max_connections = max_connections
        if bool(self.certfile) != bool(self.keyfile):
            raise ValueError("certfile and keyfile must be supplied together")
        if not self.peer_id or len(self.peer_id) > MAX_PEER_ID_LENGTH:
            raise ValueError("peer_id is invalid")
        if max_connections <= 0:
            raise ValueError("max_connections must be positive")
        self._server: ThreadingHTTPServer | None = None

    def start(self) -> ThreadingHTTPServer:
        directory = self.chunks_dir
        peer_id = self.peer_id
        auth_token = self.auth_token

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"
            server_version = "FluxWave"
            sys_version = ""

            def setup(self) -> None:
                super().setup()
                self.connection.settimeout(60.0)

            def _authorized(self) -> bool:
                if not auth_token:
                    return True
                supplied = self.headers.get("Authorization", "")
                prefix = "Bearer "
                if not supplied.startswith(prefix):
                    return False
                return hmac.compare_digest(supplied[len(prefix):], auth_token)

            def do_GET(self) -> None:
                if not self._authorized():
                    self.send_response(401)
                    self.send_header("WWW-Authenticate", "Bearer")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                path = self.path.split("?", 1)[0]
                if path == "/health":
                    self._send_bytes(
                        json.dumps({"status": "ok", "peer_id": peer_id}).encode(),
                        "application/json",
                    )
                    return
                if path == "/manifest.json":
                    self._send_file(directory / "manifest.json", "application/json")
                    return
                if path.startswith("/chunk/") and path.endswith(".chunk"):
                    name = path.rsplit("/", 1)[-1]
                    if not name[:-6].isdigit() or len(name[:-6]) > 12:
                        self.send_error(404)
                        return
                    self._send_file(directory / name, "application/octet-stream")
                    return
                self.send_error(404)

            def _headers(self, content_type: str, length: int) -> None:
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(length))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Connection", "keep-alive")

            def _send_bytes(self, payload: bytes, content_type: str) -> None:
                self.send_response(200)
                self._headers(content_type, len(payload))
                self.end_headers()
                self.wfile.write(payload)

            def _send_file(self, path: Path, content_type: str) -> None:
                try:
                    resolved = path.resolve()
                    resolved.relative_to(directory)
                except ValueError:
                    self.send_error(404)
                    return
                if not resolved.is_file():
                    self.send_error(404)
                    return
                self.send_response(200)
                self._headers(content_type, resolved.stat().st_size)
                self.end_headers()
                with resolved.open("rb") as handle:
                    while True:
                        block = handle.read(1024 * 1024)
                        if not block:
                            break
                        self.wfile.write(block)

            def log_message(self, format: str, *args: object) -> None:
                return

        class LimitedThreadingHTTPServer(ThreadingHTTPServer):
            daemon_threads = True
            request_queue_size = 32

            def process_request_thread(self, request, client_address):
                active = getattr(self, "_active", 0)
                if active >= self.max_connections:
                    request.close()
                    return
                self._active = active + 1
                try:
                    super().process_request_thread(request, client_address)
                finally:
                    self._active -= 1

        LimitedThreadingHTTPServer.max_connections = self.max_connections
        server = LimitedThreadingHTTPServer((self.host, self.port), Handler)
        if self.certfile and self.keyfile:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.minimum_version = ssl.TLSVersion.TLSv1_2
            context.load_cert_chain(self.certfile, self.keyfile)
            server.socket = context.wrap_socket(server.socket, server_side=True)
        self._server = server
        self.port = server.server_address[1]
        return server

    def serve_forever(self) -> None:
        server = self.start()
        scheme = "https" if self.certfile else "http"
        print(f"FluxWave peer listening on {scheme}://{self.host}:{self.port}")
        try:
            server.serve_forever()
        finally:
            server.server_close()

    def shutdown(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()


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
    auth_token: str | None = None,
) -> dict[str, PeerStats]:
    """Resume across peers and retry failed chunks on another peer."""
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
            manifest = PersistentPeerClient(
                peer.base_url,
                timeout=timeout,
                verify_tls=verify_tls,
                auth_token=auth_token,
            ).get_json("/manifest.json")
            break
        except Exception:
            continue
    if manifest is None:
        raise ConnectionError("no peer could provide a manifest")
    if not isinstance(manifest.get("chunks"), list) or len(manifest["chunks"]) > MAX_MANIFEST_CHUNKS:
        raise ValueError("peer manifest is invalid or too large")

    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    expected = [str(item) for item in manifest["chunks"]]
    jobs = [
        (i, digest)
        for i, digest in enumerate(expected)
        if not _verify_existing(output / f"{i:06d}.chunk", digest)
    ]

    stats = {peer.peer_id: PeerStats(peer.peer_id) for peer in normalized}
    controllers = {
        peer.peer_id: CongestionController(min(2, workers_per_peer), workers_per_peer)
        for peer in normalized
    }
    clients = {
        peer.peer_id: PersistentPeerClient(
            peer.base_url,
            timeout=timeout,
            verify_tls=verify_tls,
            auth_token=auth_token,
        )
        for peer in normalized
    }

    def fetch(job: tuple[int, str]) -> None:
        index, digest = job
        tried: set[str] = set()
        last_error: Exception | None = None
        for _ in range(max_retries):
            choices = [p for p in normalized if p.peer_id not in tried] or normalized
            peer = min(
                choices,
                key=lambda p: (stats[p.peer_id].failures, -stats[p.peer_id].throughput_mbps),
            )
            tried.add(peer.peer_id)
            controllers[peer.peer_id].acquire()
            started = time.monotonic()
            try:
                received = clients[peer.peer_id].download_chunk(
                    index, digest, output / f"{index:06d}.chunk"
                )
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

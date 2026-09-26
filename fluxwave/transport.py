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
    def __init__(self, base_url: str, *, timeout: float = 60.0, verify_tls: bool = True, auth_token: str | None = None) -> None:
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
            connection = http.client.HTTPSConnection(self.parsed.hostname, self.parsed.port, timeout=self.timeout, context=context)
        else:
            connection = http.client.HTTPConnection(self.parsed.hostname, self.parsed.port, timeout=self.timeout)
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
            value = json.loads(response.read().decode("utf-8"))
            if not isinstance(value, dict):
                raise ValueError("peer JSON response must be an object")
            return value
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
    def __init__(self, chunks_dir: str | Path, host: str = "127.0.0.1", port: int = 8765, *, peer_id: str = "fluxwave-peer", certfile: str | Path | None = None, keyfile: str | Path | None = None, auth_token: str | None = None, max_connections: int = 64) -> None:
        self.chunks_dir = Path(chunks_dir).resolve()
        self.host = host
        self.port = port
        self.peer_id = peer_id
        self.certfile = Path(certfile) if certfile else None
        self.keyfile = Path(keyfile) if keyfile else None
        self.auth_token = auth_token
        self.max_connections = max_connections
        self._httpd: ThreadingHTTPServer | None = None
        self._semaphore = threading.BoundedSemaphore(max_connections)
    def start(self) -> ThreadingHTTPServer:
        chunks_dir = self.chunks_dir
        peer_id = self.peer_id
        auth_token = self.auth_token
        semaphore = self._semaphore
        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"
            def _authorized(self) -> bool:
                if auth_token is None:
                    return True
                presented = self.headers.get("Authorization", "")
                return hmac.compare_digest(presented, f"Bearer {auth_token}")
            def _send_json(self, status: int, value: dict[str, object]) -> None:
                payload = json.dumps(value).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.end_headers()
                self.wfile.write(payload)
            def do_GET(self) -> None:
                if not semaphore.acquire(blocking=False):
                    self._send_json(503, {"error": "server busy"})
                    return
                try:
                    if not self._authorized():
                        self._send_json(401, {"error": "unauthorized"})
                        return
                    if self.path == "/health":
                        self._send_json(200, {"status": "ok", "peer_id": peer_id})
                        return
                    if self.path == "/manifest.json":
                        manifest_path = chunks_dir / "manifest.json"
                        if not manifest_path.is_file():
                            self._send_json(404, {"error": "manifest not found"})
                            return
                        payload = manifest_path.read_bytes()
                        self.send_response(200)
                        self.send_header("Content-Type", "application/json")
                        self.send_header("Content-Length", str(len(payload)))
                        self.send_header("Cache-Control", "no-store")
                        self.send_header("X-Content-Type-Options", "nosniff")
                        self.end_headers()
                        self.wfile.write(payload)
                        return
                    prefix = "/chunk/"
                    if not self.path.startswith(prefix) or not self.path.endswith(".chunk"):
                        self._send_json(404, {"error": "not found"})
                        return
                    filename = self.path[len(prefix):]
                    if "/" in filename or "\\" in filename or filename.startswith("."):
                        self._send_json(404, {"error": "not found"})
                        return
                    target = (chunks_dir / filename).resolve()
                    if chunks_dir not in target.parents or not target.is_file():
                        self._send_json(404, {"error": "not found"})
                        return
                    size = target.stat().st_size
                    self.send_response(200)
                    self.send_header("Content-Type", "application/octet-stream")
                    self.send_header("Content-Length", str(size))
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("X-Content-Type-Options", "nosniff")
                    self.end_headers()
                    with target.open("rb") as handle:
                        while block := handle.read(1024 * 1024):
                            self.wfile.write(block)
                finally:
                    semaphore.release()
            def log_message(self, format: str, *args: object) -> None:
                return
        self._httpd = ThreadingHTTPServer((self.host, self.port), Handler)
        self._httpd.daemon_threads = True
        self._httpd.allow_reuse_address = True
        self.port = self._httpd.server_address[1]
        if self.certfile and self.keyfile:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.minimum_version = ssl.TLSVersion.TLSv1_2
            context.load_cert_chain(self.certfile, self.keyfile)
            self._httpd.socket = context.wrap_socket(self._httpd.socket, server_side=True)
        return self._httpd
    def serve_forever(self) -> None:
        if self._httpd is None:
            self.start()
        assert self._httpd is not None
        self._httpd.serve_forever()
    def shutdown(self) -> None:
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()

def _verify_existing(path: Path, expected_digest: str) -> bool:
    if not path.is_file():
        return False
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest() == expected_digest

def _load_manifest_from_peer(peer: PeerEndpoint, *, timeout: float, verify_tls: bool, auth_token: str | None) -> dict[str, object] | None:
    try:
        return PersistentPeerClient(peer.base_url, timeout=timeout, verify_tls=verify_tls, auth_token=auth_token).get_json("/manifest.json")
    except Exception:
        return None

def download_from_peer(base_url: str, output_dir: str | Path, *, workers: int = 2, timeout: float = 60.0, verify_tls: bool = True, auth_token: str | None = None) -> dict[str, PeerStats]:
    """Backward-compatible single-peer wrapper around the multi-peer engine."""
    if workers <= 0:
        raise ValueError("workers must be positive")
    return download_from_peers([PeerEndpoint("peer-0", base_url)], output_dir, workers_per_peer=workers, timeout=timeout, verify_tls=verify_tls, auth_token=auth_token)

def download_from_peers(peers: list[PeerEndpoint], output_dir: str | Path, *, workers_per_peer: int = 2, max_retries: int = 3, timeout: float = 60.0, verify_tls: bool = True, auth_token: str | None = None) -> dict[str, PeerStats]:
    """Resume across peers and retry failed chunks on another peer."""
    if not peers:
        raise ValueError("at least one peer is required")
    if workers_per_peer <= 0 or max_retries <= 0:
        raise ValueError("workers_per_peer and max_retries must be positive")
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    normalized = list({peer.peer_id: peer for peer in peers}.values())
    manifest = next((candidate for peer in normalized if (candidate := _load_manifest_from_peer(peer, timeout=timeout, verify_tls=verify_tls, auth_token=auth_token)) is not None), None)
    if manifest is None:
        raise ConnectionError("no peer could provide a manifest")
    chunks = manifest.get("chunks")
    if not isinstance(chunks, list) or len(chunks) > MAX_MANIFEST_CHUNKS:
        raise ValueError("peer manifest is invalid or too large")
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    expected = [str(item) for item in chunks]
    jobs = [(i, digest) for i, digest in enumerate(expected) if not _verify_existing(output / f"{i:06d}.chunk", digest)]
    stats = {peer.peer_id: PeerStats(peer.peer_id) for peer in normalized}
    clients = {peer.peer_id: PersistentPeerClient(peer.base_url, timeout=timeout, verify_tls=verify_tls, auth_token=auth_token) for peer in normalized}
    controllers = {peer.peer_id: CongestionController(1, workers_per_peer) for peer in normalized}
    lock = threading.Lock()
    job_iter = iter(jobs)
    def worker(peer: PeerEndpoint) -> None:
        client = clients[peer.peer_id]
        controller = controllers[peer.peer_id]
        while True:
            with lock:
                try:
                    index, digest = next(job_iter)
                except StopIteration:
                    return
            destination = output / f"{index:06d}.chunk"
            controller.acquire()
            started = time.monotonic()
            try:
                received = client.download_chunk(index, digest, destination)
            except Exception:
                with lock:
                    stats[peer.peer_id].failures += 1
                controller.failure()
            else:
                elapsed = time.monotonic() - started
                with lock:
                    stats[peer.peer_id].successes += 1
                    stats[peer.peer_id].bytes_received += received
                    stats[peer.peer_id].elapsed_seconds += elapsed
                controller.success()
    with ThreadPoolExecutor(max_workers=len(normalized) * workers_per_peer) as executor:
        futures = [executor.submit(worker, peer) for peer in normalized for _ in range(workers_per_peer)]
        for future in as_completed(futures):
            future.result()
    remaining = [index for index, digest in jobs if not _verify_existing(output / f"{index:06d}.chunk", digest)]
    if remaining:
        raise ConnectionError(f"failed to download {len(remaining)} chunks")
    return stats

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from urllib.parse import urlparse


class FluxWaveHTTPServer:
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


def _download(url: str) -> bytes:
    with urlopen(url, timeout=60) as response:
        return response.read()


def _download_range(url: str, start: int, end: int) -> bytes:
    request = Request(url, headers={"Range": f"bytes={start}-{end}"})
    with urlopen(request, timeout=60) as response:
        return response.read()


def download_from_peer(
    base_url: str,
    output_dir: str | Path,
    *,
    workers: int = 4,
) -> Path:
    """Download missing chunks in parallel and verify each SHA-256 digest.

    Existing verified chunks are skipped, making interrupted downloads resumable.
    """
    if workers <= 0:
        raise ValueError("workers must be positive")

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    base = base_url.rstrip("/")

    manifest = json.loads(_download(f"{base}/manifest.json").decode("utf-8"))
    manifest_path = output / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    jobs: list[tuple[int, str]] = []
    for index, expected_digest in enumerate(manifest["chunks"]):
        path = output / f"{index:06d}.chunk"
        if path.is_file():
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest == expected_digest:
                continue
            path.unlink()
        jobs.append((index, expected_digest))

    def fetch(item: tuple[int, str]) -> int:
        index, expected_digest = item
        url = f"{base}/chunk/{index:06d}.chunk"
        payload = _download(url)
        if hashlib.sha256(payload).hexdigest() != expected_digest:
            raise ValueError(f"checksum mismatch for chunk {index}")
        temporary = output / f".{index:06d}.chunk.part"
        temporary.write_bytes(payload)
        temporary.replace(output / f"{index:06d}.chunk")
        return index

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(fetch, job) for job in jobs]
        for future in as_completed(futures):
            future.result()

    return manifest_path

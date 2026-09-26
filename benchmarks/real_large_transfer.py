from __future__ import annotations

import argparse
from hashlib import sha256
from pathlib import Path
import shutil
import tempfile
import threading
import time

from fluxwave.core.file_transfer import reconstruct_file, split_file
from fluxwave.core.manifest import load_manifest
from fluxwave.transport import FluxWaveHTTPServer, PeerEndpoint, download_from_peers


def make_file(path: Path, size: int) -> str:
    digest = sha256()
    block = bytes((index * 31 + 17) % 256 for index in range(1024 * 1024))
    remaining = size
    with path.open("wb") as handle:
        while remaining:
            payload = block[: min(len(block), remaining)]
            handle.write(payload)
            digest.update(payload)
            remaining -= len(payload)
    return digest.hexdigest()


def run(size_mib: int, chunk_mib: int) -> None:
    with tempfile.TemporaryDirectory(prefix="fluxwave-benchmark-") as temp:
        root = Path(temp)
        source = root / "large.bin"
        expected_digest = make_file(source, size_mib * 1024 * 1024)

        peer_a_dir = root / "peer-a"
        peer_b_dir = root / "peer-b"
        split_file(source, peer_a_dir, chunk_mib * 1024 * 1024)
        shutil.copytree(peer_a_dir, peer_b_dir)

        servers = [
            FluxWaveHTTPServer(peer_a_dir, "127.0.0.1", 0, peer_id="A"),
            FluxWaveHTTPServer(peer_b_dir, "127.0.0.1", 0, peer_id="B"),
        ]
        threads = []
        for server in servers:
            httpd = server.start()
            thread = threading.Thread(target=httpd.serve_forever, daemon=True)
            thread.start()
            threads.append(thread)

        try:
            one_peer = root / "one-peer"
            started = time.perf_counter()
            download_from_peers(
                [PeerEndpoint("A", f"http://127.0.0.1:{servers[0].port}")],
                one_peer,
                workers_per_peer=4,
            )
            one_elapsed = time.perf_counter() - started

            two_peers = root / "two-peers"
            started = time.perf_counter()
            download_from_peers(
                [
                    PeerEndpoint("A", f"http://127.0.0.1:{servers[0].port}"),
                    PeerEndpoint("B", f"http://127.0.0.1:{servers[1].port}"),
                ],
                two_peers,
                workers_per_peer=4,
            )
            two_elapsed = time.perf_counter() - started

            manifest = load_manifest(two_peers / "manifest.json")
            restored = root / "restored.bin"
            reconstruct_file(two_peers, manifest, restored)
            actual_digest = sha256(restored.read_bytes()).hexdigest()

            print(f"file_mib={size_mib}")
            print(f"chunk_mib={chunk_mib}")
            print(f"one_peer_seconds={one_elapsed:.3f}")
            print(f"two_peer_seconds={two_elapsed:.3f}")
            print(f"speedup={one_elapsed / two_elapsed:.2f}x")
            print(f"sha256_ok={actual_digest == expected_digest}")
        finally:
            for server in servers:
                server.shutdown()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--size-mib", type=int, default=128)
    parser.add_argument("--chunk-mib", type=int, default=4)
    args = parser.parse_args()
    run(args.size_mib, args.chunk_mib)

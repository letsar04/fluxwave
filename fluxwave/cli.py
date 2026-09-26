from __future__ import annotations

import argparse
from pathlib import Path
import os
import socket

from .core.file_transfer import reconstruct_file, split_file
from .core.manifest import load_manifest
from .discovery import advertise, discover
from .transport import FluxWaveHTTPServer, PeerEndpoint, download_from_peers


def _read_secret(path: Path | None) -> str | None:
    if path is None:
        return os.environ.get("FLUXWAVE_AUTH_TOKEN")
    value = path.read_text(encoding="utf-8").strip()
    return value or None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fluxwave",
        description="Chunk, verify, share, and reconstruct files with FluxWave.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    split = sub.add_parser("split", help="split a file into verified chunks")
    split.add_argument("source", type=Path)
    split.add_argument("output", type=Path)
    split.add_argument("--chunk-size", type=int, default=4 * 1024 * 1024)

    reconstruct = sub.add_parser("reconstruct", help="reconstruct a file from chunks")
    reconstruct.add_argument("chunks", type=Path)
    reconstruct.add_argument("manifest", type=Path)
    reconstruct.add_argument("output", type=Path)

    serve = sub.add_parser("serve", help="serve chunks over HTTP or HTTPS")
    serve.add_argument("chunks", type=Path)
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8765)
    serve.add_argument("--peer-id", default="fluxwave-peer")
    serve.add_argument("--certfile", type=Path)
    serve.add_argument("--keyfile", type=Path)
    serve.add_argument("--auth-token-file", type=Path)
    serve.add_argument("--advertise", action="store_true")
    serve.add_argument("--insecure-http", action="store_true", help="allow plaintext HTTP for isolated development only")

    download = sub.add_parser("download", help="download chunks from one or more peers")
    download.add_argument("output", type=Path)
    download.add_argument("--peer", action="append", default=[])
    download.add_argument("--workers", type=int, default=4)
    download.add_argument("--retries", type=int, default=3)
    download.add_argument("--auth-token-file", type=Path)
    download.add_argument("--insecure", action="store_true", help="disable TLS certificate verification for isolated tests only")

    discover_cmd = sub.add_parser("discover", help="discover FluxWave peers on the LAN")
    discover_cmd.add_argument("--timeout", type=float, default=3.0)

    return parser


def main() -> int:
    args = build_parser().parse_args()

    if args.command == "split":
        manifest = split_file(args.source, args.output, args.chunk_size)
        print(f"created {len(manifest.chunks)} chunks")
        print(f"manifest: {args.output / 'manifest.json'}")
        print(f"sha256: {manifest.file_digest}")
        return 0

    if args.command == "reconstruct":
        manifest = load_manifest(args.manifest)
        output = reconstruct_file(args.chunks, manifest, args.output)
        print(f"reconstructed: {output}")
        print(f"sha256: {manifest.file_digest}")
        return 0

    if args.command == "serve":
        if not args.insecure_http and not (args.certfile and args.keyfile):
            raise SystemExit("Refusing plaintext HTTP. Provide --certfile/--keyfile or explicitly use --insecure-http for isolated development.")
        token = _read_secret(args.auth_token_file)
        if not token:
            raise SystemExit("Authentication token required. Set FLUXWAVE_AUTH_TOKEN or use --auth-token-file.")
        server = FluxWaveHTTPServer(
            args.chunks,
            args.host,
            args.port,
            peer_id=args.peer_id,
            certfile=args.certfile,
            keyfile=args.keyfile,
            auth_token=token,
        )
        if args.advertise:
            import threading
            scheme = "https" if args.certfile else "http"
            thread = threading.Thread(
                target=advertise,
                args=(PeerEndpoint(args.peer_id, f"{scheme}://{socket.gethostbyname(socket.gethostname())}:{args.port}"),),
                daemon=True,
            )
            thread.start()
        server.serve_forever()
        return 0

    if args.command == "discover":
        peers = discover(timeout=args.timeout)
        for peer in peers:
            print(f"{peer.peer_id}\t{peer.base_url}")
        return 0

    if args.command == "download":
        peers = [
            PeerEndpoint(f"peer-{index}", url)
            for index, url in enumerate(args.peer, start=1)
        ]
        if not peers:
            peers = discover()
        stats = download_from_peers(
            peers,
            args.output,
            workers_per_peer=args.workers,
            max_retries=args.retries,
            verify_tls=not args.insecure,
            auth_token=_read_secret(args.auth_token_file),
        )
        for peer_id, stat in stats.items():
            print(
                f"{peer_id}: chunks={stat.successes} failures={stat.failures} "
                f"throughput={stat.throughput_mbps:.2f} Mbps"
            )
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())

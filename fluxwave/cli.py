from __future__ import annotations

import argparse
from pathlib import Path

from .core.file_transfer import reconstruct_file, split_file
from .core.manifest import load_manifest
from .discovery import advertise, discover
from .transport import FluxWaveHTTPServer, PeerEndpoint, download_from_peer, download_from_peers


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
    serve.add_argument("--host", default="0.0.0.0")
    serve.add_argument("--port", type=int, default=8765)
    serve.add_argument("--peer-id", default="fluxwave-peer")
    serve.add_argument("--certfile", type=Path)
    serve.add_argument("--keyfile", type=Path)
    serve.add_argument("--advertise", action="store_true")

    download = sub.add_parser("download", help="download chunks from one or more peers")
    download.add_argument("url", nargs="?")
    download.add_argument("output", type=Path)
    download.add_argument("--peer", action="append", default=[])
    download.add_argument("--workers", type=int, default=4)
    download.add_argument("--retries", type=int, default=3)
    download.add_argument("--insecure", action="store_true")

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
        server = FluxWaveHTTPServer(
            args.chunks,
            args.host,
            args.port,
            peer_id=args.peer_id,
            certfile=args.certfile,
            keyfile=args.keyfile,
        )
        if args.advertise:
            import threading
            thread = threading.Thread(
                target=advertise,
                args=(PeerEndpoint(args.peer_id, f"{'https' if args.certfile else 'http'}://{args.host}:{args.port}"),),
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
        peers = []
        if args.url:
            peers.append(PeerEndpoint("peer-0", args.url))
        peers.extend(
            PeerEndpoint(f"peer-{index}", url)
            for index, url in enumerate(args.peer, start=1)
        )
        if not peers:
            peers = discover()
        stats = download_from_peers(
            peers,
            args.output,
            workers_per_peer=args.workers,
            max_retries=args.retries,
            verify_tls=not args.insecure,
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

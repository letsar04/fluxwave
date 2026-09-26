from __future__ import annotations

import argparse
from pathlib import Path

from .core.file_transfer import reconstruct_file, split_file
from .core.manifest import load_manifest
from .transport import FluxWaveHTTPServer, download_from_peer


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

    serve = sub.add_parser("serve", help="serve a chunk directory to LAN peers")
    serve.add_argument("chunks", type=Path)
    serve.add_argument("--host", default="0.0.0.0")
    serve.add_argument("--port", type=int, default=8765)

    download = sub.add_parser("download", help="download verified chunks from a peer")
    download.add_argument("url")
    download.add_argument("output", type=Path)
    download.add_argument("--workers", type=int, default=4)

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
        FluxWaveHTTPServer(args.chunks, args.host, args.port).serve_forever()
        return 0

    if args.command == "download":
        manifest = download_from_peer(args.url, args.output, workers=args.workers)
        print(f"downloaded manifest: {manifest}")
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())

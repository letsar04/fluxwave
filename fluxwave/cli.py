from __future__ import annotations

import argparse
from pathlib import Path

from .core.file_transfer import split_file
from .core.manifest import load_manifest
from .core.file_transfer import reconstruct_file


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fluxwave",
        description="Chunk, manifest, and reconstruct files with FluxWave.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    split = sub.add_parser("split", help="split a file into content-addressed chunks")
    split.add_argument("source", type=Path)
    split.add_argument("output", type=Path)
    split.add_argument("--chunk-size", type=int, default=4 * 1024 * 1024)

    reconstruct = sub.add_parser("reconstruct", help="reconstruct a file from chunks")
    reconstruct.add_argument("chunks", type=Path)
    reconstruct.add_argument("manifest", type=Path)
    reconstruct.add_argument("output", type=Path)

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

    return 1


if __name__ == "__main__":
    raise SystemExit(main())

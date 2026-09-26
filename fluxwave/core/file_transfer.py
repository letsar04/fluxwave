from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from .codec import XorParityCodec
from .manifest import FileManifest, save_manifest


def build_manifest(path: str | Path, chunk_size: int) -> FileManifest:
    source = Path(path)
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")

    file_hash = sha256()
    chunks: list[str] = []
    total = 0

    with source.open("rb") as handle:
        while True:
            payload = handle.read(chunk_size)
            if not payload:
                break
            chunks.append(sha256(payload).hexdigest())
            file_hash.update(payload)
            total += len(payload)

    return FileManifest(
        filename=source.name,
        size_bytes=total,
        chunk_size=chunk_size,
        chunks=tuple(chunks),
        file_digest=file_hash.hexdigest(),
    )


def split_file(path: str | Path, output_dir: str | Path, chunk_size: int) -> FileManifest:
    source = Path(path)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    manifest = build_manifest(source, chunk_size)

    with source.open("rb") as handle:
        index = 0
        while True:
            payload = handle.read(chunk_size)
            if not payload:
                break
            temporary = output / f".{index:06d}.chunk.part"
            temporary.write_bytes(payload)
            temporary.replace(output / f"{index:06d}.chunk")
            index += 1

    save_manifest(manifest, output / "manifest.json")
    return manifest


def create_xor_parity(
    chunks_dir: str | Path,
    data_indexes: list[int],
    parity_name: str = "parity.xor",
) -> Path:
    directory = Path(chunks_dir)
    chunks = [(directory / f"{index:06d}.chunk").read_bytes() for index in data_indexes]
    parity = XorParityCodec.encode(chunks)
    destination = directory / parity_name
    destination.write_bytes(parity)
    return destination


def reconstruct_file(
    chunks_dir: str | Path,
    manifest: FileManifest,
    output_path: str | Path,
) -> Path:
    directory = Path(chunks_dir)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    file_hash = sha256()
    with output.open("wb") as handle:
        for index, digest in enumerate(manifest.chunks):
            path = directory / f"{index:06d}.chunk"
            if not path.is_file():
                raise FileNotFoundError(f"missing chunk {index}: {digest}")

            chunk_hash = sha256()
            with path.open("rb") as chunk:
                while True:
                    block = chunk.read(1024 * 1024)
                    if not block:
                        break
                    chunk_hash.update(block)
                    handle.write(block)
                    file_hash.update(block)

            if chunk_hash.hexdigest() != digest:
                raise ValueError(f"checksum mismatch for chunk {index}")

    if file_hash.hexdigest() != manifest.file_digest:
        raise ValueError("reconstructed file fingerprint does not match manifest")

    if output.stat().st_size != manifest.size_bytes:
        raise ValueError("reconstructed file size does not match manifest")

    return output

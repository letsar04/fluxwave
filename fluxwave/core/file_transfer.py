from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from .codec import XorParityCodec
from .manifest import FileManifest, save_manifest


def build_manifest(path: str | Path, chunk_size: int) -> FileManifest:
    source = Path(path)
    data = source.read_bytes()
    chunks = [
        sha256(data[offset : offset + chunk_size]).hexdigest()
        for offset in range(0, len(data), chunk_size)
    ]
    return FileManifest(
        filename=source.name,
        size_bytes=len(data),
        chunk_size=chunk_size,
        chunks=tuple(chunks),
        file_digest=sha256(data).hexdigest(),
    )


def split_file(path: str | Path, output_dir: str | Path, chunk_size: int) -> FileManifest:
    source = Path(path)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    data = source.read_bytes()
    manifest = build_manifest(source, chunk_size)

    for index, offset in enumerate(range(0, len(data), chunk_size)):
        (output / f"{index:06d}.chunk").write_bytes(data[offset : offset + chunk_size])

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
    with output.open("wb") as handle:
        for digest in manifest.chunks:
            matches = [
                path
                for path in directory.glob("*.chunk")
                if sha256(path.read_bytes()).hexdigest() == digest
            ]
            if not matches:
                raise FileNotFoundError(f"missing chunk: {digest}")
            handle.write(matches[0].read_bytes())

    if sha256(output.read_bytes()).hexdigest() != manifest.file_digest:
        raise ValueError("reconstructed file fingerprint does not match manifest")

    return output

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path


@dataclass(frozen=True)
class Chunk:
    index: int
    offset: int
    size: int
    digest: str


def chunk_bytes(data: bytes, chunk_size: int = 1024 * 1024) -> list[Chunk]:
    """Describe fixed-size chunks without copying their payloads."""
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")

    chunks: list[Chunk] = []
    for index, offset in enumerate(range(0, len(data), chunk_size)):
        payload = data[offset : offset + chunk_size]
        chunks.append(
            Chunk(
                index=index,
                offset=offset,
                size=len(payload),
                digest=sha256(payload).hexdigest(),
            )
        )
    return chunks


def chunk_file(path: str | Path, chunk_size: int = 1024 * 1024) -> list[Chunk]:
    """Build a deterministic chunk manifest for a file."""
    return chunk_bytes(Path(path).read_bytes(), chunk_size)

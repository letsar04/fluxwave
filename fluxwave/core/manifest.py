from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path


@dataclass(frozen=True)
class FileManifest:
    filename: str
    size_bytes: int
    chunk_size: int
    chunks: tuple[str, ...]
    file_digest: str

    def to_dict(self) -> dict[str, object]:
        return {
            "filename": self.filename,
            "size_bytes": self.size_bytes,
            "chunk_size": self.chunk_size,
            "chunks": list(self.chunks),
            "file_digest": self.file_digest,
        }

    @classmethod
    def from_dict(cls, value: dict[str, object]) -> "FileManifest":
        return cls(
            filename=str(value["filename"]),
            size_bytes=int(value["size_bytes"]),
            chunk_size=int(value["chunk_size"]),
            chunks=tuple(str(item) for item in value["chunks"]),
            file_digest=str(value["file_digest"]),
        )


def save_manifest(manifest: FileManifest, path: str | Path) -> None:
    Path(path).write_text(
        json.dumps(manifest.to_dict(), indent=2),
        encoding="utf-8",
    )


def load_manifest(path: str | Path) -> FileManifest:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    return FileManifest.from_dict(value)

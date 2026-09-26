from __future__ import annotations

import hashlib
from pathlib import Path


class ChunkStore:
    """Persistent content-addressed local chunk store."""

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, digest: str) -> Path:
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise ValueError("digest must be a lowercase SHA-256 hex string")
        return self.root / digest[:2] / digest

    def has(self, digest: str) -> bool:
        path = self.path_for(digest)
        return path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == digest

    def put(self, data: bytes) -> str:
        digest = hashlib.sha256(data).hexdigest()
        path = self.path_for(digest)
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_bytes(data)
        return digest

    def get(self, digest: str) -> bytes:
        path = self.path_for(digest)
        if not self.has(digest):
            raise FileNotFoundError(digest)
        return path.read_bytes()

    def delete(self, digest: str) -> None:
        path = self.path_for(digest)
        if path.exists():
            path.unlink()

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import json
from urllib.parse import urlparse


@dataclass(frozen=True)
class PeerInfo:
    peer_id: str
    base_url: str


@dataclass(frozen=True)
class ChunkInfo:
    index: int
    digest: str
    size_bytes: int


def canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign_manifest(manifest: dict[str, object], secret: bytes) -> str:
    payload = canonical_json(manifest)
    return hmac.new(secret, payload, hashlib.sha256).hexdigest()


def verify_manifest_signature(
    manifest: dict[str, object],
    signature: str,
    secret: bytes,
) -> bool:
    expected = sign_manifest(manifest, secret)
    return hmac.compare_digest(expected, signature)


def validate_peer_url(base_url: str) -> str:
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("peer URL must use http:// or https://")
    return base_url.rstrip("/")

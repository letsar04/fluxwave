from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256


class CodecError(ValueError):
    """Raised when encoded fragments cannot be reconstructed safely."""


@dataclass(frozen=True)
class XorParityCodec:
    """Minimal byte-level reconstruction codec.

    For a group of equal-length data fragments D0..Dn, parity P is the bytewise
    XOR of all data fragments. Any one missing fragment can be reconstructed as
    P XOR every other available data fragment.

    This is a real codec backend, while the reconstruction planner remains
    codec-agnostic.
    """

    @staticmethod
    def encode(data_fragments: list[bytes]) -> bytes:
        if not data_fragments:
            raise CodecError("at least one data fragment is required")
        size = len(data_fragments[0])
        if any(len(fragment) != size for fragment in data_fragments):
            raise CodecError("all fragments must have the same size")

        parity = bytearray(size)
        for fragment in data_fragments:
            for i, value in enumerate(fragment):
                parity[i] ^= value
        return bytes(parity)

    @staticmethod
    def reconstruct(
        parity: bytes,
        available_data: list[bytes],
        *,
        fragment_count: int,
    ) -> bytes:
        if fragment_count <= 0:
            raise CodecError("fragment_count must be positive")
        if len(available_data) != fragment_count - 1:
            raise CodecError("exactly one data fragment must be missing")
        if any(len(fragment) != len(parity) for fragment in available_data):
            raise CodecError("all fragments must have the same size as parity")

        result = bytearray(parity)
        for fragment in available_data:
            for i, value in enumerate(fragment):
                result[i] ^= value
        return bytes(result)

    @staticmethod
    def fingerprint(data: bytes) -> str:
        return sha256(data).hexdigest()

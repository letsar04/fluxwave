from __future__ import annotations

from dataclasses import dataclass
import math
import random


@dataclass(frozen=True)
class Peer:
    peer_id: str
    bandwidth_mbps: float
    latency_ms: float
    failure_probability: float = 0.0

    def __post_init__(self) -> None:
        if self.bandwidth_mbps <= 0:
            raise ValueError("bandwidth_mbps must be positive")
        if self.latency_ms < 0:
            raise ValueError("latency_ms cannot be negative")
        if not 0 <= self.failure_probability <= 1:
            raise ValueError("failure_probability must be between 0 and 1")


@dataclass(frozen=True)
class TransferResult:
    success: bool
    elapsed_seconds: float
    transferred_bytes: int
    attempts: int
    failures: int


def transfer_time_seconds(size_bytes: int, peer: Peer) -> float:
    """Idealized one-shot transfer time for a fragment."""
    if size_bytes < 0:
        raise ValueError("size_bytes cannot be negative")
    return size_bytes * 8 / (peer.bandwidth_mbps * 1_000_000) + peer.latency_ms / 1000


def simulate_transfer(
    size_bytes: int,
    peer: Peer,
    *,
    rng: random.Random | None = None,
    max_attempts: int = 100,
) -> TransferResult:
    """Simulate repeated fragment attempts under an independent failure model.

    Failed attempts consume their full modeled transfer time. This deliberately
    simple model gives us a deterministic baseline for comparing schedulers.
    """
    if size_bytes < 0:
        raise ValueError("size_bytes cannot be negative")
    if max_attempts <= 0:
        raise ValueError("max_attempts must be positive")

    generator = rng or random.Random()
    one_attempt = transfer_time_seconds(size_bytes, peer)
    attempts = 0
    failures = 0

    while attempts < max_attempts:
        attempts += 1
        if generator.random() >= peer.failure_probability:
            return TransferResult(
                success=True,
                elapsed_seconds=one_attempt * attempts,
                transferred_bytes=size_bytes * attempts,
                attempts=attempts,
                failures=failures,
            )
        failures += 1

    return TransferResult(
        success=False,
        elapsed_seconds=one_attempt * attempts,
        transferred_bytes=size_bytes * attempts,
        attempts=attempts,
        failures=failures,
    )


def parallel_transfer_time(size_bytes: int, peers: list[Peer]) -> float:
    """Lower-bound time when equal work is split perfectly across peers."""
    if not peers:
        raise ValueError("at least one peer is required")
    total_bandwidth = math.fsum(peer.bandwidth_mbps for peer in peers)
    max_latency = max(peer.latency_ms for peer in peers) / 1000
    return size_bytes * 8 / (total_bandwidth * 1_000_000) + max_latency

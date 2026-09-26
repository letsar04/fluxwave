from __future__ import annotations

from dataclasses import dataclass
import random

from fluxwave.network import Peer, simulate_transfer


@dataclass(frozen=True)
class Aggregate:
    trials: int
    success_rate: float
    mean_seconds: float
    mean_bytes: float


def benchmark(peer: Peer, *, size_bytes: int, trials: int = 1000, seed: int = 42) -> Aggregate:
    if trials <= 0:
        raise ValueError("trials must be positive")

    rng = random.Random(seed)
    results = [simulate_transfer(size_bytes, peer, rng=rng) for _ in range(trials)]
    return Aggregate(
        trials=trials,
        success_rate=sum(r.success for r in results) / trials,
        mean_seconds=sum(r.elapsed_seconds for r in results) / trials,
        mean_bytes=sum(r.transferred_bytes for r in results) / trials,
    )


def main() -> None:
    peers = [
        Peer("fast-reliable", 100, 20, 0.01),
        Peer("slow-reliable", 30, 5, 0.001),
        Peer("fast-fragile", 100, 20, 0.20),
    ]
    for peer in peers:
        result = benchmark(peer, size_bytes=4 * 1024 * 1024)
        print(
            f"{peer.peer_id}: success={result.success_rate:.3f} "
            f"mean_time={result.mean_seconds:.4f}s "
            f"mean_bytes={result.mean_bytes / 1024**2:.2f} MiB"
        )


if __name__ == "__main__":
    main()

from __future__ import annotations

import random

from scenarios import SCENARIOS
from fluxwave.network import simulate_transfer


CHUNK_SIZE = 4 * 1024 * 1024


def run() -> None:
    for scenario_name, peers in SCENARIOS.items():
        print(f"\n[{scenario_name}]")
        for peer in peers:
            result = simulate_transfer(
                CHUNK_SIZE,
                peer,
                rng=random.Random(42),
            )
            print(
                f"{peer.peer_id}: success={result.success} "
                f"time={result.elapsed_seconds:.4f}s "
                f"attempts={result.attempts} "
                f"transferred={result.transferred_bytes / 1024**2:.2f} MiB"
            )


if __name__ == "__main__":
    run()

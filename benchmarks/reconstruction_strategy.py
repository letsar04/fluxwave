from __future__ import annotations

from fluxwave.core.planner import FragmentCandidate, PeerState, expected_transfer_cost
from fluxwave.core.reconstruction import ReconstructionGraph, ReconstructionRule
from fluxwave.core.state import DestinationState


def main() -> None:
    peers = [
        PeerState("slow-source", 10, 20, 0.0),
        PeerState("fast-source", 100, 5, 0.0),
    ]
    fragments = {"A": 4_000_000, "B": 4_000_000, "C": 8_000_000}

    graph = ReconstructionGraph()
    graph.register(ReconstructionRule("C", ("A", "B"), cpu_cost_seconds=0.02))

    destination = DestinationState(frozenset({"A"}))

    direct = expected_transfer_cost(
        FragmentCandidate("C", "slow-source", fragments["C"]),
        peers[0],
    )
    decision = graph.best_decision(
        "C",
        [FragmentCandidate("C", "slow-source", fragments["C"])],
        destination,
        fragments,
        peers,
    )

    print("FluxWave reconstruction strategy")
    print(f"direct_cost_seconds={direct:.4f}")
    print(f"chosen_strategy={decision.strategy if decision else 'unresolved'}")
    print(f"chosen_cost_seconds={decision.cost_seconds if decision else float('inf'):.4f}")
    print(f"additional_transfers={list(decision.transfer_fragments) if decision else []}")


if __name__ == "__main__":
    main()

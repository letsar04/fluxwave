from __future__ import annotations

from fluxwave.core.graph import FragmentAvailabilityIndex, FragmentNode
from fluxwave.core.planner import PeerState
from fluxwave.core.scheduler import schedule_fragment_options
from fluxwave.core.state import DestinationState


def build_demo():
    fragments = [FragmentNode(f"f{i}", 4_000_000) for i in range(6)]
    peers = [
        PeerState("A", 120, 20, 0.01),
        PeerState("B", 35, 5, 0.001),
        PeerState("C", 70, 80, 0.04),
    ]
    index = FragmentAvailabilityIndex()
    index.register_many("A", ["f0", "f1", "f2", "f4"])
    index.register_many("B", ["f1", "f2", "f3", "f5"])
    index.register_many("C", ["f0", "f3", "f4", "f5"])
    destination = DestinationState(frozenset({"f0"}))
    return fragments, peers, index, destination


def main() -> None:
    fragments, peers, index, destination = build_demo()
    options = index.candidates(fragments, destination, peers)
    schedule = schedule_fragment_options(options, peers)

    total = sum(fragment.size_bytes for fragment in fragments)
    required = sum(fragment.size_bytes for fragment in fragments if fragment.fragment_id not in destination.available_fragments)
    unresolved = index.unresolved(fragments, destination)

    print("FluxWave graph reconstruction demo")
    print(f"total_bytes={total}")
    print(f"required_bytes={required}")
    print(f"scheduled_bytes={sum(next(c.size_bytes for c in options[f.fragment_id] if c.peer_id == f.peer_id) for f in schedule.fragments):.0f}")
    print(f"unresolved={list(unresolved)}")
    print(f"makespan_seconds={schedule.makespan_seconds:.4f}")
    for item in schedule.fragments:
        print(f"{item.fragment_id} <- {item.peer_id}: {item.expected_seconds:.4f}s")


if __name__ == "__main__":
    main()

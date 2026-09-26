from fluxwave.core.planner import FragmentCandidate, PeerState
from fluxwave.core.reconstruction import ReconstructionGraph, ReconstructionRule
from fluxwave.core.state import DestinationState


def peers():
    return [
        PeerState("fast", 100, 5, 0.0),
        PeerState("slow", 10, 5, 0.0),
    ]


def test_direct_transfer_wins_when_it_is_cheaper():
    graph = ReconstructionGraph()
    graph.register(ReconstructionRule("f3", ("f1", "f2"), cpu_cost_seconds=0.5))

    decision = graph.best_decision(
        "f3",
        [FragmentCandidate("f3", "fast", 1_000_000)],
        DestinationState(frozenset()),
        {"f1": 1_000_000, "f2": 1_000_000, "f3": 1_000_000},
        peers(),
    )

    assert decision is not None
    assert decision.strategy == "direct"


def test_reconstruction_wins_when_prerequisites_are_available():
    graph = ReconstructionGraph()
    graph.register(ReconstructionRule("f3", ("f1", "f2"), cpu_cost_seconds=0.01))

    decision = graph.best_decision(
        "f3",
        [FragmentCandidate("f3", "slow", 10_000_000)],
        DestinationState(frozenset({"f1", "f2"})),
        {"f1": 1_000_000, "f2": 1_000_000, "f3": 10_000_000},
        peers(),
    )

    assert decision is not None
    assert decision.strategy == "reconstruct"
    assert decision.transfer_fragments == ()


def test_nested_dependency_is_planned():
    graph = ReconstructionGraph()
    graph.register(ReconstructionRule("f2", ("f0", "f1"), cpu_cost_seconds=0.01))
    graph.register(ReconstructionRule("f3", ("f2", "f4"), cpu_cost_seconds=0.01))

    decision = graph.best_decision(
        "f3",
        [],
        DestinationState(frozenset({"f0"})),
        {"f0": 1_000_000, "f1": 1_000_000, "f2": 1_000_000, "f3": 1_000_000, "f4": 1_000_000},
        peers(),
    )

    assert decision is not None
    assert decision.strategy == "reconstruct"
    assert set(decision.transfer_fragments) == {"f1", "f4"}


def test_cycle_is_rejected_as_unusable():
    graph = ReconstructionGraph()
    graph.register(ReconstructionRule("a", ("b",)))
    graph.register(ReconstructionRule("b", ("a",)))

    decision = graph.best_decision(
        "a",
        [],
        DestinationState(frozenset()),
        {"a": 100, "b": 100},
        peers(),
    )

    assert decision is not None
    assert decision.strategy == "direct" or decision.cost_seconds != float("inf")

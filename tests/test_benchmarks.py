from benchmarks.oracle import oracle_schedule
from benchmarks.strategies import fastest_schedule, random_schedule
from fluxwave.core.planner import FragmentCandidate, PeerState
from fluxwave.core.scheduler import schedule_fragments


def scenario():
    peers = [
        PeerState("a", 100, 10, 0.0),
        PeerState("b", 50, 10, 0.0),
        PeerState("c", 20, 5, 0.0),
    ]
    candidates = [
        FragmentCandidate("1", "source", 1_000_000),
        FragmentCandidate("2", "source", 2_000_000),
        FragmentCandidate("3", "source", 3_000_000),
        FragmentCandidate("4", "source", 4_000_000),
    ]
    return candidates, peers


def test_oracle_is_no_worse_than_heuristics():
    candidates, peers = scenario()
    oracle = oracle_schedule(candidates, peers)
    warp = schedule_fragments(candidates, peers)
    fastest = fastest_schedule(candidates, peers)
    random = random_schedule(candidates, peers, seed=7)

    assert oracle.makespan_seconds <= warp.makespan_seconds
    assert oracle.makespan_seconds <= fastest.makespan_seconds
    assert oracle.makespan_seconds <= random.makespan_seconds


def test_oracle_assigns_every_fragment():
    candidates, peers = scenario()
    result = oracle_schedule(candidates, peers)
    assert {item.fragment_id for item in result.fragments} == {c.fragment_id for c in candidates}

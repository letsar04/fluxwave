from fluxwave.core.planner import FragmentCandidate, PeerState
from fluxwave.core.scheduler import schedule_fragments


def test_scheduler_assigns_fragments_to_available_peers():
    peers = [
        PeerState("fast", 100, 10, 0.0),
        PeerState("slow", 20, 10, 0.0),
    ]
    candidates = [
        FragmentCandidate("a", "source", 5_000_000),
        FragmentCandidate("b", "source", 5_000_000),
        FragmentCandidate("c", "source", 5_000_000),
    ]

    schedule = schedule_fragments(candidates, peers)

    assert len(schedule.fragments) == 3
    assert {item.peer_id for item in schedule.fragments} == {"fast"}
    assert schedule.makespan_seconds > 0


def test_unusable_peer_is_skipped():
    peers = [
        PeerState("dead", 100, 10, 1.0),
        PeerState("live", 10, 10, 0.0),
    ]
    candidates = [FragmentCandidate("a", "source", 1_000_000)]

    schedule = schedule_fragments(candidates, peers)

    assert schedule.fragments[0].peer_id == "live"

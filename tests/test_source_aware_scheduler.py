from fluxwave.core.planner import FragmentCandidate, PeerState
from fluxwave.core.scheduler import schedule_fragment_options


def test_source_aware_scheduler_never_uses_unadvertised_peer():
    peers = [
        PeerState("advertised", 100, 10, 0.0),
        PeerState("unadvertised", 1_000, 1, 0.0),
    ]
    options = {
        "f1": [FragmentCandidate("f1", "advertised", 1_000_000)],
    }

    schedule = schedule_fragment_options(options, peers)

    assert len(schedule.fragments) == 1
    assert schedule.fragments[0].peer_id == "advertised"


def test_source_aware_scheduler_never_schedules_same_fragment_twice():
    peers = [
        PeerState("a", 100, 10, 0.0),
        PeerState("b", 100, 10, 0.0),
    ]
    options = {
        "f1": [
            FragmentCandidate("f1", "a", 1_000_000),
            FragmentCandidate("f1", "b", 1_000_000),
        ],
    }

    schedule = schedule_fragment_options(options, peers)

    assert len(schedule.fragments) == 1
    assert schedule.fragments[0].fragment_id == "f1"

from fluxwave.core.planner import FragmentCandidate, PeerState, expected_attempts, expected_transfer_cost, score


def test_expected_attempts_matches_geometric_model():
    peer = PeerState("p", 100, 10, 0.2)
    assert expected_attempts(peer) == 1.25


def test_reliable_peer_can_beat_faster_unreliable_peer():
    candidate = FragmentCandidate("f", "reliable", 10_000_000)
    reliable = PeerState("reliable", 50, 5, 0.0)
    unreliable = PeerState("unreliable", 100, 5, 0.6)

    assert expected_transfer_cost(candidate, reliable) < expected_transfer_cost(candidate, unreliable)
    assert score(candidate, reliable) > score(candidate, unreliable)

from fluxwave.core.planner import FragmentCandidate, PeerState, rank_candidates


def test_warp_prefers_fast_reliable_peer_for_equal_fragments():
    peers = [
        PeerState("slow", bandwidth_mbps=10, latency_ms=20, failure_probability=0.01),
        PeerState("fast", bandwidth_mbps=100, latency_ms=20, failure_probability=0.01),
    ]
    candidates = [
        FragmentCandidate("f1", "slow", 1_000_000),
        FragmentCandidate("f1", "fast", 1_000_000),
    ]

    ranked = rank_candidates(candidates, peers)
    assert ranked[0][0].peer_id == "fast"

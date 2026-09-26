from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PeerState:
    peer_id: str
    bandwidth_mbps: float
    latency_ms: float
    failure_probability: float = 0.0


@dataclass(frozen=True)
class FragmentCandidate:
    fragment_id: str
    peer_id: str
    size_bytes: int
    reconstruction_gain: float = 1.0


def expected_attempts(peer: PeerState) -> float:
    """Expected number of attempts under independent failure."""
    if not 0 <= peer.failure_probability < 1:
        return float("inf")
    return 1.0 / (1.0 - peer.failure_probability)


def transfer_time(candidate: FragmentCandidate, peer: PeerState) -> float:
    if peer.bandwidth_mbps <= 0:
        return float("inf")
    return candidate.size_bytes * 8 / (peer.bandwidth_mbps * 1_000_000) + peer.latency_ms / 1000.0


def expected_transfer_cost(candidate: FragmentCandidate, peer: PeerState) -> float:
    """Expected wall-clock cost including retransmission risk."""
    base = transfer_time(candidate, peer)
    attempts = expected_attempts(peer)
    return base * attempts if attempts != float("inf") else float("inf")


def transfer_cost(candidate: FragmentCandidate, peer: PeerState) -> float:
    """Backward-compatible alias for the expected cost."""
    return expected_transfer_cost(candidate, peer)


def score(candidate: FragmentCandidate, peer: PeerState) -> float:
    """WARP score: expected reconstruction gain per expected second."""
    cost = expected_transfer_cost(candidate, peer)
    if cost == float("inf"):
        return 0.0
    return candidate.reconstruction_gain / cost


def rank_candidates(
    candidates: list[FragmentCandidate], peers: list[PeerState]
) -> list[tuple[FragmentCandidate, float]]:
    peer_map = {peer.peer_id: peer for peer in peers}
    ranked = []
    for candidate in candidates:
        peer = peer_map.get(candidate.peer_id)
        if peer is None:
            continue
        ranked.append((candidate, score(candidate, peer)))
    return sorted(ranked, key=lambda item: item[1], reverse=True)

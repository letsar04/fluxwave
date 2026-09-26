from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PeerState:
    peer_id: str
    bandwidth_mbps: float
    latency_ms: float
    failure_probability: float


@dataclass(frozen=True)
class FragmentCandidate:
    fragment_id: str
    peer_id: str
    size_bytes: int
    reconstruction_gain: float = 1.0


def transfer_cost(candidate: FragmentCandidate, peer: PeerState) -> float:
    """Estimate normalized cost; lower is better."""
    if peer.bandwidth_mbps <= 0:
        return float("inf")
    seconds = candidate.size_bytes * 8 / (peer.bandwidth_mbps * 1_000_000)
    failure_multiplier = 1.0 + max(0.0, peer.failure_probability)
    return (seconds + peer.latency_ms / 1000.0) * failure_multiplier


def score(candidate: FragmentCandidate, peer: PeerState) -> float:
    """WARP score: higher means a more attractive transfer candidate."""
    cost = transfer_cost(candidate, peer)
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

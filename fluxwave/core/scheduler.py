from __future__ import annotations

from dataclasses import dataclass

from .planner import FragmentCandidate, PeerState, expected_transfer_cost

@dataclass(frozen=True)
class ScheduledFragment:
    fragment_id: str
    peer_id: str
    start_seconds: float
    finish_seconds: float
    expected_seconds: float

@dataclass(frozen=True)
class Schedule:
    fragments: tuple[ScheduledFragment, ...]
    makespan_seconds: float

def schedule_fragment_options(options_by_fragment: dict[str, list[FragmentCandidate]], peers: list[PeerState]) -> Schedule:
    """Schedule each logical fragment exactly once using only valid source peers."""
    peer_map = {peer.peer_id: peer for peer in peers}
    availability = {peer.peer_id: 0.0 for peer in peers}
    scheduled: list[ScheduledFragment] = []
    ordered = sorted(options_by_fragment.items(), key=lambda item: max((c.size_bytes for c in item[1]), default=0), reverse=True)
    for fragment_id, candidates in ordered:
        options = []
        for candidate in candidates:
            peer = peer_map.get(candidate.peer_id)
            if peer is None:
                continue
            cost = expected_transfer_cost(candidate, peer)
            if cost == float("inf"):
                continue
            start = availability[peer.peer_id]
            options.append((start + cost, cost, peer.peer_id, start))
        if not options:
            continue
        finish, cost, peer_id, start = min(options)
        scheduled.append(ScheduledFragment(fragment_id, peer_id, start, finish, cost))
        availability[peer_id] = finish
    return Schedule(tuple(scheduled), max((item.finish_seconds for item in scheduled), default=0.0))

def schedule_fragments(candidates: list[FragmentCandidate], peers: list[PeerState]) -> Schedule:
    """Backward-compatible scheduler where every peer is a possible source."""
    options: dict[str, list[FragmentCandidate]] = {}
    for candidate in candidates:
        options.setdefault(candidate.fragment_id, []).extend(
            FragmentCandidate(candidate.fragment_id, peer.peer_id, candidate.size_bytes) for peer in peers
        )
    return schedule_fragment_options(options, peers)

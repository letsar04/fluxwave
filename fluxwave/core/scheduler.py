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


def schedule_fragments(
    candidates: list[FragmentCandidate], peers: list[PeerState]
) -> Schedule:
    """Greedily minimize the predicted makespan with peer-local availability.

    Each fragment is assigned to the peer that gives the earliest predicted
    completion time. Ties are broken by lower expected transfer cost, then peer id.
    This is intentionally a transparent heuristic rather than an exact optimizer.
    """
    peer_map = {peer.peer_id: peer for peer in peers}
    availability = {peer.peer_id: 0.0 for peer in peers}
    scheduled: list[ScheduledFragment] = []

    ordered = sorted(candidates, key=lambda c: c.size_bytes, reverse=True)
    for candidate in ordered:
        options = []
        for peer_id, available_at in availability.items():
            peer = peer_map[peer_id]
            cost = expected_transfer_cost(candidate, peer)
            if cost == float("inf"):
                continue
            finish = available_at + cost
            options.append((finish, cost, peer_id, available_at))

        if not options:
            continue

        finish, cost, peer_id, start = min(options)
        scheduled.append(
            ScheduledFragment(
                fragment_id=candidate.fragment_id,
                peer_id=peer_id,
                start_seconds=start,
                finish_seconds=finish,
                expected_seconds=cost,
            )
        )
        availability[peer_id] = finish

    makespan = max((item.finish_seconds for item in scheduled), default=0.0)
    return Schedule(tuple(scheduled), makespan)

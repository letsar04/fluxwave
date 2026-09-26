from __future__ import annotations

from itertools import product

from fluxwave.core.planner import FragmentCandidate, PeerState, expected_transfer_cost
from fluxwave.core.scheduler import Schedule, ScheduledFragment


def oracle_schedule(candidates: list[FragmentCandidate], peers: list[PeerState]) -> Schedule:
    """Find the minimum-makespan assignment by exhaustive enumeration.

    This is deliberately limited to small candidate sets and exists only as a
    ground-truth reference for evaluating heuristics.
    """
    if not candidates or not peers:
        return Schedule((), 0.0)

    best_makespan = float("inf")
    best_assignment = None

    valid = []
    for candidate in candidates:
        choices = [
            peer for peer in peers
            if expected_transfer_cost(candidate, peer) != float("inf")
        ]
        if not choices:
            return Schedule((), float("inf"))
        valid.append(choices)

    for assignment in product(*valid):
        loads = {peer.peer_id: 0.0 for peer in peers}
        for candidate, peer in zip(candidates, assignment):
            loads[peer.peer_id] += expected_transfer_cost(candidate, peer)
        makespan = max(loads.values())
        if makespan < best_makespan:
            best_makespan = makespan
            best_assignment = assignment

    availability = {peer.peer_id: 0.0 for peer in peers}
    scheduled = []
    for candidate, peer in zip(candidates, best_assignment):
        cost = expected_transfer_cost(candidate, peer)
        start = availability[peer.peer_id]
        finish = start + cost
        availability[peer.peer_id] = finish
        scheduled.append(ScheduledFragment(candidate.fragment_id, peer.peer_id, start, finish, cost))

    return Schedule(tuple(scheduled), best_makespan)

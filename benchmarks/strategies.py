from __future__ import annotations

import random

from fluxwave.core.planner import FragmentCandidate, PeerState, expected_transfer_cost
from fluxwave.core.scheduler import Schedule, ScheduledFragment


def random_schedule(candidates: list[FragmentCandidate], peers: list[PeerState], seed: int = 42) -> Schedule:
    rng = random.Random(seed)
    availability = {peer.peer_id: 0.0 for peer in peers}
    peer_map = {peer.peer_id: peer for peer in peers}
    items: list[ScheduledFragment] = []

    for candidate in candidates:
        choices = [peer for peer in peers if expected_transfer_cost(candidate, peer) != float("inf")]
        if not choices:
            continue
        peer = rng.choice(choices)
        cost = expected_transfer_cost(candidate, peer)
        start = availability[peer.peer_id]
        finish = start + cost
        availability[peer.peer_id] = finish
        items.append(ScheduledFragment(candidate.fragment_id, peer.peer_id, start, finish, cost))

    return Schedule(tuple(items), max((item.finish_seconds for item in items), default=0.0))


def fastest_schedule(candidates: list[FragmentCandidate], peers: list[PeerState]) -> Schedule:
    availability = {peer.peer_id: 0.0 for peer in peers}
    items: list[ScheduledFragment] = []

    for candidate in sorted(candidates, key=lambda c: c.size_bytes, reverse=True):
        options = []
        for peer in peers:
            cost = expected_transfer_cost(candidate, peer)
            if cost != float("inf"):
                options.append((peer.bandwidth_mbps, cost, peer.peer_id, peer))
        if not options:
            continue
        _, cost, _, peer = max(options, key=lambda x: (x[0], -x[1]))
        start = availability[peer.peer_id]
        finish = start + cost
        availability[peer.peer_id] = finish
        items.append(ScheduledFragment(candidate.fragment_id, peer.peer_id, start, finish, cost))

    return Schedule(tuple(items), max((item.finish_seconds for item in items), default=0.0))

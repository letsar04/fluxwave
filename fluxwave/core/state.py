from __future__ import annotations

from dataclasses import dataclass

from .planner import FragmentCandidate


@dataclass(frozen=True)
class DestinationState:
    """Fragments already verified at the destination."""
    available_fragments: frozenset[str]

    def missing(self, candidates: list[FragmentCandidate]) -> list[FragmentCandidate]:
        return [c for c in candidates if c.fragment_id not in self.available_fragments]


def saved_bytes(candidates: list[FragmentCandidate], state: DestinationState) -> int:
    return sum(c.size_bytes for c in candidates if c.fragment_id in state.available_fragments)


def required_bytes(candidates: list[FragmentCandidate], state: DestinationState) -> int:
    return sum(c.size_bytes for c in state.missing(candidates))

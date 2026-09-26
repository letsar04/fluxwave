from __future__ import annotations

from dataclasses import dataclass, field

from .planner import FragmentCandidate, PeerState
from .state import DestinationState


@dataclass(frozen=True)
class FragmentNode:
    fragment_id: str
    size_bytes: int
    digest: str | None = None


@dataclass
class FragmentAvailabilityIndex:
    """Bipartite fragment -> peer availability index.

    The index deliberately uses dict/set primitives instead of a graph library:
    availability is the hot path and the representation is easy to serialize.
    """

    _sources: dict[str, set[str]] = field(default_factory=dict)

    def register(self, fragment_id: str, peer_id: str) -> None:
        self._sources.setdefault(fragment_id, set()).add(peer_id)

    def register_many(self, peer_id: str, fragment_ids: list[str]) -> None:
        for fragment_id in fragment_ids:
            self.register(fragment_id, peer_id)

    def sources(self, fragment_id: str) -> tuple[str, ...]:
        return tuple(sorted(self._sources.get(fragment_id, set())))

    def unresolved(self, fragments: list[FragmentNode], destination: DestinationState) -> tuple[str, ...]:
        return tuple(
            fragment.fragment_id
            for fragment in fragments
            if fragment.fragment_id not in destination.available_fragments
            and not self._sources.get(fragment.fragment_id)
        )

    def candidates(
        self,
        fragments: list[FragmentNode],
        destination: DestinationState,
        peers: list[PeerState],
    ) -> dict[str, list[FragmentCandidate]]:
        """Build one logical fragment with all currently valid source choices."""
        peer_ids = {peer.peer_id for peer in peers}
        result: dict[str, list[FragmentCandidate]] = {}

        for fragment in fragments:
            if fragment.fragment_id in destination.available_fragments:
                continue

            choices = [
                FragmentCandidate(fragment.fragment_id, peer_id, fragment.size_bytes)
                for peer_id in self.sources(fragment.fragment_id)
                if peer_id in peer_ids
            ]
            if choices:
                result[fragment.fragment_id] = choices

        return result

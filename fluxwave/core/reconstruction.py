from __future__ import annotations

from dataclasses import dataclass

from .planner import FragmentCandidate, PeerState, expected_transfer_cost
from .state import DestinationState


@dataclass(frozen=True)
class ReconstructionRule:
    """Logical rule describing how a target fragment can be synthesized.

    The rule is intentionally codec-agnostic: it models planning cost before
    any byte-level reconstruction implementation is selected.
    """

    target_fragment: str
    source_fragments: tuple[str, ...]
    cpu_cost_seconds: float = 0.0

    def __post_init__(self) -> None:
        if not self.target_fragment:
            raise ValueError("target_fragment cannot be empty")
        if not self.source_fragments:
            raise ValueError("source_fragments cannot be empty")
        if self.target_fragment in self.source_fragments:
            raise ValueError("a target cannot directly depend on itself")
        if self.cpu_cost_seconds < 0:
            raise ValueError("cpu_cost_seconds cannot be negative")


@dataclass(frozen=True)
class ReconstructionDecision:
    target_fragment: str
    strategy: str
    cost_seconds: float
    transfer_fragments: tuple[str, ...] = ()
    rule: ReconstructionRule | None = None


class ReconstructionGraph:
    """Dependency graph used by WARP to compare direct transfer and synthesis."""

    def __init__(self) -> None:
        self._rules: dict[str, list[ReconstructionRule]] = {}

    def register(self, rule: ReconstructionRule) -> None:
        self._rules.setdefault(rule.target_fragment, []).append(rule)

    def rules_for(self, target_fragment: str) -> tuple[ReconstructionRule, ...]:
        return tuple(self._rules.get(target_fragment, ()))

    def best_decision(
        self,
        target_fragment: str,
        direct_candidates: list[FragmentCandidate],
        destination: DestinationState,
        fragments: dict[str, int],
        peers: list[PeerState],
    ) -> ReconstructionDecision | None:
        peer_map = {peer.peer_id: peer for peer in peers}
        direct_options = []
        for candidate in direct_candidates:
            peer = peer_map.get(candidate.peer_id)
            if peer is None:
                continue
            cost = expected_transfer_cost(candidate, peer)
            if cost != float("inf"):
                direct_options.append((cost, candidate))

        best: ReconstructionDecision | None = None
        if direct_options:
            cost, _ = min(direct_options, key=lambda item: item[0])
            best = ReconstructionDecision(target_fragment, "direct", cost)

        for rule in self.rules_for(target_fragment):
            cost, transfers = self._rule_cost(
                rule, destination, fragments, peers, set()
            )
            if cost == float("inf"):
                continue
            decision = ReconstructionDecision(
                target_fragment,
                "reconstruct",
                cost,
                tuple(transfers),
                rule,
            )
            if best is None or decision.cost_seconds < best.cost_seconds:
                best = decision

        return best

    def _rule_cost(
        self,
        rule: ReconstructionRule,
        destination: DestinationState,
        fragments: dict[str, int],
        peers: list[PeerState],
        visiting: set[str],
    ) -> tuple[float, list[str]]:
        if rule.target_fragment in visiting:
            return float("inf"), []
        visiting = visiting | {rule.target_fragment}

        total = rule.cpu_cost_seconds
        transfers: list[str] = []

        for source_id in rule.source_fragments:
            if source_id in destination.available_fragments:
                continue

            nested_rules = self.rules_for(source_id)
            best_source_cost = float("inf")
            best_source_transfers: list[str] = []

            for nested in nested_rules:
                nested_cost, nested_transfers = self._rule_cost(
                    nested, destination, fragments, peers, visiting
                )
                if nested_cost < best_source_cost:
                    best_source_cost = nested_cost
                    best_source_transfers = nested_transfers

            size = fragments.get(source_id)
            if size is None:
                return float("inf"), []

            for peer in peers:
                candidate = FragmentCandidate(source_id, peer.peer_id, size)
                direct_cost = expected_transfer_cost(candidate, peer)
                if direct_cost < best_source_cost:
                    best_source_cost = direct_cost
                    best_source_transfers = [source_id]

            if best_source_cost == float("inf"):
                return float("inf"), []

            total += best_source_cost
            transfers.extend(best_source_transfers)

        return total, transfers

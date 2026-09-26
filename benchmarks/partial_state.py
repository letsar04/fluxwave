from __future__ import annotations

from fluxwave.core.planner import FragmentCandidate
from fluxwave.core.state import DestinationState, required_bytes, saved_bytes


def report(candidates: list[FragmentCandidate], state: DestinationState) -> dict[str, float]:
    total = sum(c.size_bytes for c in candidates)
    saved = saved_bytes(candidates, state)
    required = required_bytes(candidates, state)
    ratio = saved / total if total else 0.0
    return {
        "total_bytes": total,
        "saved_bytes": saved,
        "required_bytes": required,
        "saved_ratio": ratio,
    }


def main() -> None:
    candidates = [FragmentCandidate(f"f{i}", "source", 1_000_000) for i in range(10)]
    state = DestinationState(frozenset({"f0", "f2", "f4", "f6"}))
    print(report(candidates, state))


if __name__ == "__main__":
    main()

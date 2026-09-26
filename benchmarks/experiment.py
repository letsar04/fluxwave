from __future__ import annotations

from dataclasses import dataclass
import random
import statistics

from benchmarks.oracle import oracle_schedule
from benchmarks.strategies import fastest_schedule, random_schedule
from fluxwave.core.planner import FragmentCandidate, PeerState
from fluxwave.core.scheduler import schedule_fragments


@dataclass(frozen=True)
class Measurement:
    scenario: str
    strategy: str
    trials: int
    mean: float
    median: float
    p95: float
    gap_percent: float


def percentile(values: list[float], q: float) -> float:
    values = sorted(values)
    return values[min(len(values) - 1, int((len(values) - 1) * q))]


def build_scenario(rng: random.Random, name: str):
    peers = []
    for i in range(rng.randint(3, 5)):
        failure = rng.uniform(0, 0.02) if name == "stable" else rng.uniform(0.05, 0.35)
        latency = rng.uniform(5, 180) if name == "high-latency" else rng.uniform(2, 80)
        peers.append(PeerState(f"p{i}", rng.uniform(10, 200), latency, failure))
    candidates = [FragmentCandidate(f"f{i}", "source", rng.randint(250_000, 8_000_000)) for i in range(rng.randint(4, 8))]
    return candidates, peers


def run(trials: int = 100, seed: int = 42) -> list[Measurement]:
    scenarios = ["stable", "fragile", "high-latency"]
    strategies = {
        "random": lambda c, p, s: random_schedule(c, p, seed=s),
        "fastest": lambda c, p, s: fastest_schedule(c, p),
        "warp": lambda c, p, s: schedule_fragments(c, p),
        "oracle": lambda c, p, s: oracle_schedule(c, p),
    }
    out = []
    for scenario in scenarios:
        for name, strategy in strategies.items():
            values, gaps = [], []
            for trial in range(trials):
                rng = random.Random(seed + trial)
                candidates, peers = build_scenario(rng, scenario)
                oracle = oracle_schedule(candidates, peers)
                result = strategy(candidates, peers, seed + trial)
                values.append(result.makespan_seconds)
                gaps.append((result.makespan_seconds - oracle.makespan_seconds) / oracle.makespan_seconds * 100)
            out.append(Measurement(scenario, name, len(values), statistics.mean(values), statistics.median(values), percentile(values, .95), statistics.mean(gaps)))
    return out


def main() -> None:
    print("scenario,strategy,trials,mean,median,p95,gap_percent")
    for m in run():
        print(f"{m.scenario},{m.strategy},{m.trials},{m.mean:.6f},{m.median:.6f},{m.p95:.6f},{m.gap_percent:.2f}")


if __name__ == "__main__":
    main()

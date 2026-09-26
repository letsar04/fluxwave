from __future__ import annotations

from fluxwave.network import Peer


PEERS = [
    Peer("A", bandwidth_mbps=100, latency_ms=20, failure_probability=0.01),
    Peer("B", bandwidth_mbps=30, latency_ms=5, failure_probability=0.001),
    Peer("C", bandwidth_mbps=70, latency_ms=80, failure_probability=0.04),
    Peer("D", bandwidth_mbps=15, latency_ms=10, failure_probability=0.0),
]

SCENARIOS = {
    "stable": PEERS,
    "fragile-fast": [
        Peer("A", 100, 20, 0.15),
        Peer("B", 30, 5, 0.001),
        Peer("C", 70, 80, 0.20),
        Peer("D", 15, 10, 0.0),
    ],
    "asymmetric": [
        Peer("A", 200, 120, 0.02),
        Peer("B", 25, 2, 0.0),
        Peer("C", 40, 15, 0.01),
    ],
}

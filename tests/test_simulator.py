import random

import pytest

from fluxwave.network import Peer, parallel_transfer_time, simulate_transfer


def test_invalid_peer_values_are_rejected() -> None:
    with pytest.raises(ValueError):
        Peer("x", 0, 10)
    with pytest.raises(ValueError):
        Peer("x", 10, -1)
    with pytest.raises(ValueError):
        Peer("x", 10, 10, 1.1)


def test_zero_failure_succeeds_on_first_attempt() -> None:
    peer = Peer("x", 100, 10, 0.0)
    result = simulate_transfer(1_000_000, peer, rng=random.Random(1))
    assert result.success
    assert result.attempts == 1
    assert result.failures == 0


def test_deterministic_failures_can_exhaust_attempts() -> None:
    peer = Peer("x", 100, 10, 1.0)
    result = simulate_transfer(1_000_000, peer, rng=random.Random(1), max_attempts=3)
    assert not result.success
    assert result.attempts == 3
    assert result.failures == 3


def test_parallel_time_uses_aggregate_bandwidth() -> None:
    peers = [Peer("a", 100, 10), Peer("b", 100, 20)]
    result = parallel_transfer_time(10_000_000, peers)
    assert result == pytest.approx(0.42)

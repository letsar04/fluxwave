from benchmarks.experiment import percentile, run


def test_percentile_is_deterministic():
    assert percentile([1.0, 2.0, 3.0, 4.0], 0.95) == 4.0


def test_experiment_is_reproducible():
    first = run(trials=2, seed=10)
    second = run(trials=2, seed=10)
    assert first == second

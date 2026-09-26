from benchmarks.graph_reconstruction import build_demo
from fluxwave.core.scheduler import schedule_fragment_options


def test_graph_demo_schedules_each_missing_fragment_once():
    fragments, peers, index, destination = build_demo()
    options = index.candidates(fragments, destination, peers)

    schedule = schedule_fragment_options(options, peers)

    assert len(schedule.fragments) == 5
    assert len({item.fragment_id for item in schedule.fragments}) == 5
    assert all(item.fragment_id != "f0" for item in schedule.fragments)

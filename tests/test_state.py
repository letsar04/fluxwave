from fluxwave.core.planner import FragmentCandidate
from fluxwave.core.state import DestinationState, required_bytes, saved_bytes


def test_partial_destination_excludes_existing_fragments():
    candidates = [
        FragmentCandidate("a", "p", 100),
        FragmentCandidate("b", "p", 200),
        FragmentCandidate("c", "p", 300),
    ]
    state = DestinationState(frozenset({"a", "c"}))

    assert [c.fragment_id for c in state.missing(candidates)] == ["b"]
    assert saved_bytes(candidates, state) == 400
    assert required_bytes(candidates, state) == 200

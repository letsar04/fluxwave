from fluxwave.core.graph import FragmentAvailabilityIndex, FragmentNode
from fluxwave.core.planner import PeerState
from fluxwave.core.state import DestinationState


def test_fragment_can_have_multiple_sources():
    index = FragmentAvailabilityIndex()
    index.register("f1", "peer-a")
    index.register("f1", "peer-b")

    assert index.sources("f1") == ("peer-a", "peer-b")


def test_destination_fragments_are_not_replanned():
    index = FragmentAvailabilityIndex()
    index.register("f1", "peer-a")
    index.register("f2", "peer-b")
    fragments = [FragmentNode("f1", 100), FragmentNode("f2", 200)]
    destination = DestinationState(frozenset({"f1"}))
    peers = [PeerState("peer-a", 100, 1), PeerState("peer-b", 100, 1)]

    candidates = index.candidates(fragments, destination, peers)

    assert list(candidates) == ["f2"]
    assert candidates["f2"][0].peer_id == "peer-b"


def test_unresolved_fragment_is_explicit():
    index = FragmentAvailabilityIndex()
    fragments = [FragmentNode("missing", 100)]
    destination = DestinationState(frozenset())

    assert index.unresolved(fragments, destination) == ("missing",)

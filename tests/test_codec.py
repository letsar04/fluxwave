from fluxwave.core.codec import CodecError, XorParityCodec


def test_xor_round_trip_with_one_missing_fragment():
    fragments = [
        bytes(range(64)),
        bytes((value * 3) % 256 for value in range(64)),
        bytes((255 - value) % 256 for value in range(64)),
    ]
    parity = XorParityCodec.encode(fragments)

    recovered = XorParityCodec.reconstruct(
        parity,
        [fragments[0], fragments[2]],
        fragment_count=3,
    )

    assert recovered == fragments[1]


def test_xor_rejects_different_fragment_sizes():
    try:
        XorParityCodec.encode([b"a", b"bb"])
    except CodecError:
        pass
    else:
        raise AssertionError("expected CodecError")

from fluxwave.core.chunking import chunk_bytes


def test_chunking_is_deterministic():
    data = b"abcdefghij"
    first = chunk_bytes(data, chunk_size=4)
    second = chunk_bytes(data, chunk_size=4)

    assert first == second
    assert [chunk.size for chunk in first] == [4, 4, 2]
    assert first[0].offset == 0
    assert first[-1].offset == 8

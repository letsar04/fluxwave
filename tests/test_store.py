from fluxwave.store import ChunkStore


def test_chunk_store_is_content_addressed(tmp_path):
    store = ChunkStore(tmp_path / "store")
    digest = store.put(b"hello fluxwave")

    assert store.has(digest)
    assert store.get(digest) == b"hello fluxwave"
    assert store.path_for(digest).parent.name == digest[:2]


def test_chunk_store_reuses_same_content(tmp_path):
    store = ChunkStore(tmp_path / "store")
    first = store.put(b"same")
    second = store.put(b"same")

    assert first == second
    assert len(list((tmp_path / "store").rglob("*"))) == 2

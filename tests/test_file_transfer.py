from hashlib import sha256

from fluxwave.core.file_transfer import create_xor_parity, reconstruct_file, split_file


def test_split_and_reconstruct_file(tmp_path):
    source = tmp_path / "source.bin"
    source.write_bytes(bytes(range(256)) * 4)

    chunks = tmp_path / "chunks"
    manifest = split_file(source, chunks, 128)

    assert manifest.size_bytes == source.stat().st_size
    assert len(manifest.chunks) == 8

    restored = tmp_path / "restored.bin"
    reconstruct_file(chunks, manifest, restored)

    assert sha256(restored.read_bytes()).hexdigest() == manifest.file_digest


def test_create_xor_parity(tmp_path):
    source = tmp_path / "source.bin"
    source.write_bytes(bytes(range(128)) * 3)

    chunks = tmp_path / "chunks"
    split_file(source, chunks, 128)
    parity = create_xor_parity(chunks, [0, 1, 2])

    assert parity.exists()
    assert len(parity.read_bytes()) == 128

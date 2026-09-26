import json

from fluxwave.core.file_transfer import split_file
from fluxwave.transport import download_from_peer


def test_transport_module_imports(tmp_path):
    source = tmp_path / "source.bin"
    source.write_bytes(bytes(range(256)) * 8)

    peer_dir = tmp_path / "peer"
    split_file(source, peer_dir, 128)

    manifest = json.loads((peer_dir / "manifest.json").read_text())
    assert len(manifest["chunks"]) == 16


def test_download_rejects_invalid_worker_count(tmp_path):
    try:
        download_from_peer("http://127.0.0.1:1", tmp_path / "out", workers=0)
    except ValueError as exc:
        assert "workers" in str(exc)
    else:
        raise AssertionError("expected ValueError")

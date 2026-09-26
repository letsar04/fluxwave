import threading

import pytest

from fluxwave.core.file_transfer import split_file
from fluxwave.transport import FluxWaveHTTPServer, PersistentPeerClient


def _server(tmp_path, token=None):
    source = tmp_path / "source.bin"
    source.write_bytes(b"secure-data" * 1024)
    chunks = tmp_path / "chunks"
    split_file(source, chunks, 1024)
    server = FluxWaveHTTPServer(
        chunks,
        "127.0.0.1",
        0,
        peer_id="secure-peer",
        auth_token=token,
    )
    httpd = server.start()
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return server, thread


def test_bearer_auth_rejects_missing_token(tmp_path):
    server, thread = _server(tmp_path, token="secret-token")
    try:
        client = PersistentPeerClient(f"http://127.0.0.1:{server.port}")
        with pytest.raises(ConnectionError):
            client.get_json("/health")
    finally:
        server.shutdown()
        thread.join(timeout=1)


def test_bearer_auth_accepts_correct_token(tmp_path):
    server, thread = _server(tmp_path, token="secret-token")
    try:
        client = PersistentPeerClient(
            f"http://127.0.0.1:{server.port}", auth_token="secret-token"
        )
        assert client.get_json("/health")["peer_id"] == "secure-peer"
    finally:
        server.shutdown()
        thread.join(timeout=1)


def test_peer_url_cannot_embed_credentials():
    with pytest.raises(ValueError):
        PersistentPeerClient("https://user:password@example.com")


def test_client_rejects_path_traversal():
    client = PersistentPeerClient("http://127.0.0.1:8765")
    with pytest.raises(ValueError):
        client.get_json("/../manifest.json")

import json
import threading

from fluxwave.core.file_transfer import reconstruct_file, split_file
from fluxwave.transport import (
    FluxWaveHTTPServer,
    PeerEndpoint,
    PersistentPeerClient,
    download_from_peers,
)


def start_server(chunks_dir, peer_id):
    server = FluxWaveHTTPServer(chunks_dir, "127.0.0.1", 0, peer_id=peer_id)
    httpd = server.start()
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return server, thread


def test_real_http_download_and_resume(tmp_path):
    source = tmp_path / "source.bin"
    source.write_bytes(bytes(range(256)) * 4096)
    peer_dir = tmp_path / "peer"
    split_file(source, peer_dir, 1024)

    server, _ = start_server(peer_dir, "A")
    try:
        output = tmp_path / "out"
        result = download_from_peers(
            [PeerEndpoint("A", f"http://127.0.0.1:{server.port}")],
            output,
            workers_per_peer=3,
        )
        assert result["A"].successes > 0

        manifest = json.loads((output / "manifest.json").read_text())
        chunk = output / "000000.chunk"
        before = chunk.read_bytes()
        download_from_peers(
            [PeerEndpoint("A", f"http://127.0.0.1:{server.port}")],
            output,
            workers_per_peer=2,
        )
        assert chunk.read_bytes() == before

        restored = tmp_path / "restored.bin"
        reconstruct_file(output, __import__("fluxwave.core.manifest", fromlist=["FileManifest"]).FileManifest.from_dict(manifest), restored)
        assert restored.read_bytes() == source.read_bytes()
    finally:
        server.shutdown()


def test_failed_peer_is_recovered_by_second_peer(tmp_path):
    source = tmp_path / "source.bin"
    source.write_bytes(bytes(range(251)) * 1024)
    peer_a = tmp_path / "peer-a"
    peer_b = tmp_path / "peer-b"
    split_file(source, peer_a, 1024)
    split_file(source, peer_b, 1024)

    # Corrupt one chunk on peer A while keeping its manifest unchanged.
    bad = peer_a / "000000.chunk"
    bad.write_bytes(b"corrupted")

    server_a, _ = start_server(peer_a, "A")
    server_b, _ = start_server(peer_b, "B")
    try:
        output = tmp_path / "out"
        stats = download_from_peers(
            [
                PeerEndpoint("A", f"http://127.0.0.1:{server_a.port}"),
                PeerEndpoint("B", f"http://127.0.0.1:{server_b.port}"),
            ],
            output,
            workers_per_peer=2,
            max_retries=3,
        )
        assert stats["A"].failures >= 1
        assert stats["B"].successes >= 1
        assert (output / "000000.chunk").read_bytes() == (peer_b / "000000.chunk").read_bytes()
    finally:
        server_a.shutdown()
        server_b.shutdown()


def test_persistent_client_can_reuse_peer_connection(tmp_path):
    source = tmp_path / "source.bin"
    source.write_bytes(b"x" * 4096)
    peer_dir = tmp_path / "peer"
    split_file(source, peer_dir, 1024)

    server, _ = start_server(peer_dir, "A")
    try:
        client = PersistentPeerClient(f"http://127.0.0.1:{server.port}")
        assert client.get_json("/health")["status"] == "ok"
        manifest = client.get_json("/manifest.json")
        assert len(manifest["chunks"]) == 4
    finally:
        server.shutdown()

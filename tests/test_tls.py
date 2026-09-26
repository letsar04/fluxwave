import shutil
import subprocess
import threading

import pytest

from fluxwave.core.file_transfer import split_file
from fluxwave.transport import FluxWaveHTTPServer, PersistentPeerClient


def test_tls_peer_accepts_real_tls_connection(tmp_path):
    if shutil.which("openssl") is None:
        pytest.skip("openssl is not installed")

    source = tmp_path / "source.bin"
    source.write_bytes(b"tls-test" * 512)
    chunks = tmp_path / "chunks"
    split_file(source, chunks, 1024)

    cert = tmp_path / "server.crt"
    key = tmp_path / "server.key"
    subprocess.run(
        [
            "openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
            "-days", "1", "-keyout", str(key), "-out", str(cert),
            "-subj", "/CN=localhost",
        ],
        check=True,
        capture_output=True,
    )

    server = FluxWaveHTTPServer(
        chunks,
        "127.0.0.1",
        0,
        peer_id="tls",
        certfile=cert,
        keyfile=key,
    )
    httpd = server.start()
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        client = PersistentPeerClient(
            f"https://127.0.0.1:{server.port}",
            verify_tls=False,
        )
        assert client.get_json("/health")["peer_id"] == "tls"
    finally:
        server.shutdown()

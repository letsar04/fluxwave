import threading
import time

import pytest

from fluxwave.discovery import DiscoveryConfig, advertise, discover
from fluxwave.transport import PeerEndpoint


def test_multicast_discovery_round_trip():
    config = DiscoveryConfig(group="239.255.42.98", port=42430, interval_seconds=0.1)
    peer = PeerEndpoint("test-peer", "http://127.0.0.1:9999")

    thread = threading.Thread(
        target=advertise,
        kwargs={"peer": peer, "config": config, "stop_after": 0.8},
        daemon=True,
    )
    thread.start()
    time.sleep(0.1)

    try:
        peers = discover(config=config, timeout=1.2)
    except OSError as exc:
        pytest.skip(f"multicast unavailable in test environment: {exc}")
    finally:
        thread.join(timeout=1)

    assert any(item.peer_id == peer.peer_id for item in peers)

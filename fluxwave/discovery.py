from __future__ import annotations

from dataclasses import dataclass
import json
import socket
import time
import uuid

from .transport import PeerEndpoint


DISCOVERY_GROUP = "239.255.42.99"
DISCOVERY_PORT = 42429
DISCOVERY_MAGIC = "fluxwave/1"


@dataclass(frozen=True)
class DiscoveryConfig:
    group: str = DISCOVERY_GROUP
    port: int = DISCOVERY_PORT
    interval_seconds: float = 2.0
    ttl: int = 1


def advertise(
    peer: PeerEndpoint,
    *,
    config: DiscoveryConfig = DiscoveryConfig(),
    stop_after: float | None = None,
) -> None:
    """Broadcast a peer announcement on the local multicast segment."""
    payload = json.dumps(
        {
            "protocol": DISCOVERY_MAGIC,
            "peer_id": peer.peer_id,
            "base_url": peer.base_url,
            "nonce": uuid.uuid4().hex,
        },
        separators=(",", ":"),
    ).encode("utf-8")

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP) as sock:
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, config.ttl)
        started = time.monotonic()
        while stop_after is None or time.monotonic() - started < stop_after:
            sock.sendto(payload, (config.group, config.port))
            time.sleep(config.interval_seconds)


def discover(
    *,
    config: DiscoveryConfig = DiscoveryConfig(),
    timeout: float = 3.0,
) -> list[PeerEndpoint]:
    """Listen for announcements and return unique peers."""
    peers: dict[str, PeerEndpoint] = {}
    deadline = time.monotonic() + timeout

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("", config.port))
        membership = socket.inet_aton(config.group) + socket.inet_aton("0.0.0.0")
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, membership)
        sock.settimeout(0.25)

        while time.monotonic() < deadline:
            try:
                data, _ = sock.recvfrom(65535)
            except socket.timeout:
                continue
            try:
                value = json.loads(data.decode("utf-8"))
                if value.get("protocol") != DISCOVERY_MAGIC:
                    continue
                peer_id = str(value["peer_id"])
                base_url = str(value["base_url"])
                if peer_id and base_url:
                    peers[peer_id] = PeerEndpoint(peer_id, base_url)
            except (ValueError, KeyError, UnicodeDecodeError):
                continue

    return sorted(peers.values(), key=lambda peer: peer.peer_id)

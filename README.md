# FluxWave

**Adaptive data transfer engine for large-scale file sharing.**

FluxWave treats a large file as a set of verified fragments and chooses transfer actions using destination state, peer availability, expected transfer cost, failure risk, and reconstructibility.

> Research/engineering prototype. The network stack is suitable for controlled LAN experiments; do not expose a peer directly to the public Internet without an additional security layer and operational hardening.

## Implemented transfer stack

- streaming chunking and reconstruction for files larger than available RAM;
- SHA-256 content fingerprints;
- destination-side resume;
- persistent HTTP/1.1 connections;
- concurrent multi-peer transfer;
- checksum verification before a chunk becomes final;
- retry on another peer after a failed transfer;
- per-peer throughput/failure measurements;
- AIMD congestion control for per-peer concurrency;
- optional TLS 1.2+ transport;
- LAN multicast peer discovery;
- content-addressed local chunk store;
- dependency-aware reconstruction planning;
- WARP scheduling and real XOR parity;
- reproducible simulation benchmarks;
- a real large-file benchmark over local TCP sockets.

## Architecture

~~~text
SOURCE
  |
streaming chunker
  |
SHA-256 manifest
  |
  +-----------------------+
  |                       |
peer discovery       destination state
  |                       |
  +-----------+-----------+
              |
        WARP / scheduler
              |
      +-------+-------+
      |       |       |
    Peer A  Peer B  Peer C
      |       |       |
      +-------+-------+
              |
      persistent HTTP/1.1
              |
        TLS (optional)
              |
       verified chunks
              |
         reconstruction
~~~

## Persistent connections

PersistentPeerClient uses HTTP/1.1 keep-alive and retains one connection per worker thread. A transfer therefore does not need a new TCP/TLS handshake for every chunk.

## TLS

For a local test certificate, OpenSSL can generate one with:

~~~bash
openssl req -x509 -newkey rsa:2048 -nodes -days 30 \\
  -keyout server.key -out server.crt -subj "/CN=fluxwave"
~~~

A peer can then run with the certificate and private key:

~~~bash
fluxwave serve ./chunks --host 0.0.0.0 --port 8765 \
  --certfile server.crt --keyfile server.key
~~~

The downloader validates certificates by default. The --insecure option is available for controlled self-signed/LAN experiments only.

## Peer discovery

FluxWave uses UDP multicast on the local network:

~~~bash
fluxwave discover --timeout 5
~~~

A peer can announce itself while serving:

~~~bash
fluxwave serve ./chunks --port 8765 --peer-id node-a --advertise
~~~

Discovery is intentionally LAN-scoped. It is not a replacement for an authenticated Internet rendezvous service.

## Failure recovery

For every missing chunk, FluxWave:

1. checks whether a verified local copy already exists;
2. selects an available peer;
3. streams the chunk into a temporary file;
4. verifies SHA-256;
5. atomically commits the chunk;
6. retries from another peer after an error or checksum mismatch.

An interrupted process can therefore be restarted without retransmitting verified chunks.

## Congestion control

Each peer has an application-level AIMD window:

- successful chunks increase the window gradually;
- failures halve it;
- the window is bounded by workers-per-peer.

This is intentionally above TCP: TCP controls packets inside one connection, while FluxWave controls application-level chunk concurrency.

## CLI

Split a large file without loading it entirely into RAM:

~~~bash
fluxwave split video.mp4 ./chunks --chunk-size 4194304
~~~

Reconstruct and verify:

~~~bash
fluxwave reconstruct ./chunks ./chunks/manifest.json restored.mp4
~~~

Serve:

~~~bash
fluxwave serve ./chunks --host 0.0.0.0 --port 8765 --peer-id node-a
~~~

Download from one peer:

~~~bash
fluxwave download ./received --peer http://192.168.1.10:8765 --workers 4
~~~

Download from multiple peers:

~~~bash
fluxwave download http://192.168.1.10:8765 ./received \
  --peer http://192.168.1.11:8765 \
  --peer http://192.168.1.12:8765 \
  --workers 4 --retries 3
~~~

Or let discovery find peers:

~~~bash
fluxwave download ./received
~~~

For a self-signed TLS peer in a controlled test:

~~~bash
fluxwave download ./received --peer https://192.168.1.10:8765 --insecure
~~~

## Real large-file benchmark

The benchmark creates a deterministic file, chunks it, starts two local TCP peers, measures a single-peer transfer and a two-peer transfer, reconstructs the result, and checks the final SHA-256.

~~~bash
python benchmarks/real_large_transfer.py --size-mib 128 --chunk-mib 4
~~~

Output format:

~~~text
file_mib=128
chunk_mib=4
one_peer_seconds=...
two_peer_seconds=...
speedup=...x
sha256_ok=True
~~~

The benchmark reports measurements rather than promising a fixed speedup. Results depend on CPU, filesystem, operating system, socket buffers, and machine topology.

## Reconstruction model

A target can have logical rules such as:

~~~text
F3 = reconstruct(F1, F2)
~~~

WARP compares direct transfer with the cost of fetching missing prerequisites plus CPU reconstruction cost.

The current real codec backend is XOR parity. For equal-length fragments:

~~~text
P = F1 XOR F2 XOR ... XOR Fn
~~~

One missing fragment can therefore be recovered from parity and the remaining fragments.

## Limitations

FluxWave is not yet a public Internet file-sharing service. Production deployment still requires:

- authenticated peer identity and certificate provisioning;
- a trusted rendezvous/discovery service outside the LAN;
- stronger abuse and rate controls;
- persistent transfer-session metadata across process restarts;
- more sophisticated erasure coding than single XOR parity;
- network-wide congestion modelling;
- benchmark runs on geographically separated machines;
- formal protocol/version compatibility;
- security review.

Individual ingredients used by FluxWave—content addressing, chunked transfer, peer-to-peer scheduling, HTTP keep-alive, TLS, multicast discovery, and XOR/erasure coding—are established techniques. The research question is whether their combination, guided by reconstruction cost and destination state, produces measurable benefits for large transfers.

## Status

**Phase 3 — usable LAN transfer prototype**

The project now covers the experimental path from chunking to multi-peer transfer, TLS, discovery, recovery, congestion control, reconstruction, and real large-file benchmarking. The next step is protocol hardening and validation on heterogeneous real networks.

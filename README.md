# FluxWave

**Adaptive data transfer engine for large-scale file sharing.**

FluxWave treats a large file as a set of verified fragments and chooses transfer actions using destination state, peer availability, expected transfer cost, failure risk, and reconstructibility.

> **Enterprise-testable LAN prototype.** The secure CLI requires TLS and peer authentication by default. It is not yet a public Internet service and is not certified against any compliance standard.

## Implemented transfer stack

- streaming chunking and reconstruction for files larger than available RAM;
- SHA-256 content fingerprints;
- destination-side resume;
- persistent HTTP/1.1 connections;
- concurrent multi-peer transfer;
- bearer-token peer authentication;
- TLS 1.2+ transport;
- checksum verification before a chunk becomes final;
- retry on another peer after a failed transfer;
- bounded manifest and connection resources;
- path-boundary checks against traversal;
- per-peer throughput/failure measurements;
- AIMD congestion control for per-peer concurrency;
- LAN multicast peer discovery;
- content-addressed local chunk store;
- dependency-aware reconstruction planning;
- WARP scheduling and real XOR parity;
- reproducible simulation benchmarks;
- a real large-file benchmark over local TCP sockets;
- CI unit/integration tests, Bandit static analysis and pip-audit dependency checks.

## Security model

Security is a release gate. The secure CLI:

1. refuses plaintext HTTP unless `--insecure-http` is explicitly selected;
2. binds to `127.0.0.1` by default;
3. requires an authentication token for serving;
4. validates TLS certificates by default on the client;
5. rejects credentials embedded in peer URLs;
6. rejects path traversal attempts;
7. verifies SHA-256 before committing downloaded chunks;
8. bounds manifest size and peer connection concurrency;
9. uses socket timeouts and does not expose Python's default server identity.

Read the full threat model and operational requirements in `SECURITY.md` and the test matrix in `SECURITY_TEST_PLAN.md`.

### Secure pilot setup

Generate or obtain a certificate from your enterprise PKI. For an isolated test only, OpenSSL can create a short-lived certificate:

~~~bash
openssl req -x509 -newkey rsa:2048 -nodes -days 30 \\
  -keyout server.key -out server.crt -subj "/CN=fluxwave"
~~~

Create a token in a secret manager or protected file. Do not commit it and do not place it in a URL.

~~~bash
set FLUXWAVE_AUTH_TOKEN=replace-with-a-long-random-secret
~~~

Then serve only the intended chunk directory:

~~~bash
fluxwave serve C:\fluxwave\chunks \\
  --host 10.0.0.20 \\
  --port 8765 \\
  --certfile C:\fluxwave\server.crt \\
  --keyfile C:\fluxwave\server.key
~~~

The client can use the same secret through `FLUXWAVE_AUTH_TOKEN` or an `--auth-token-file`. Certificate verification remains enabled by default.

**Never use `--insecure` or `--insecure-http` for an enterprise deployment.**

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
         TLS + auth
              |
       verified chunks
              |
         reconstruction
~~~

## Persistent connections

`PersistentPeerClient` uses HTTP/1.1 keep-alive and retains one connection per worker thread. A transfer therefore does not need a new TCP/TLS handshake for every chunk.

## Peer discovery

FluxWave uses UDP multicast on the local network:

~~~bash
fluxwave discover --timeout 5
~~~

Discovery is a locator, not an authentication mechanism. Every discovered peer must still be authenticated before it is trusted for data transfer.

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

Secure serving:

~~~bash
fluxwave serve ./chunks \\
  --host 10.0.0.20 \\
  --port 8765 \\
  --certfile server.crt \\
  --keyfile server.key \\
  --auth-token-file C:\\secrets\\fluxwave.token
~~~

Download from one or more authenticated peers:

~~~bash
fluxwave download ./received \\
  --peer https://10.0.0.20:8765 \\
  --peer https://10.0.0.21:8765 \\
  --workers 4 \\
  --retries 3 \\
  --auth-token-file C:\\secrets\\fluxwave.token
~~~

For isolated development only, plaintext HTTP can be explicitly enabled with `--insecure-http`; this is intentionally not the default.

## Real large-file benchmark

The benchmark creates a deterministic file, chunks it, starts two local TCP peers, measures a single-peer transfer and a two-peer transfer, reconstructs the result, and checks the final SHA-256.

~~~bash
python benchmarks/real_large_transfer.py --size-mib 128 --chunk-mib 4
~~~

The benchmark reports measurements rather than promising a fixed speedup. Results depend on CPU, filesystem, operating system, socket buffers, and machine topology.

## Reconstruction model

WARP compares direct transfer with the cost of fetching missing prerequisites plus CPU reconstruction cost.

The current real codec backend is XOR parity. For equal-length fragments:

~~~text
P = F1 XOR F2 XOR ... XOR Fn
~~~

One missing fragment can therefore be recovered from parity and the remaining fragments.

## Enterprise test gate

Before a pilot, run the full test suite and security gates locally or in CI:

~~~bash
python -m pytest -q
bandit -q -r fluxwave
pip-audit
python benchmarks/real_large_transfer.py --size-mib 128 --chunk-mib 4
~~~

For the full enterprise test matrix, see `SECURITY_TEST_PLAN.md`.

## Limitations and residual risk

FluxWave is not yet a public Internet file-sharing service. Remaining production work includes:

- mutual TLS or an enterprise identity provider instead of bearer-only peer identity;
- signed manifests and stronger end-to-end sender authenticity;
- a trusted rendezvous service for cross-network discovery;
- persistent transfer-session metadata across process restarts;
- stronger rate limiting and abuse controls;
- richer erasure coding than single XOR parity;
- network-wide congestion modelling;
- geographically separated benchmark runs;
- formal protocol/version compatibility;
- independent penetration testing and security review.

Individual ingredients used by FluxWave are established techniques. The research/product hypothesis is whether their combination, guided by destination state and reconstruction cost, produces measurable benefits for large transfers.

## Status

**Phase 4 — enterprise pilot candidate for controlled networks**

The repository now has secure-by-default CLI behavior, authentication, TLS, security regression tests, static security/dependency gates, failure recovery, multi-peer transfer and real large-file benchmarks. The next release gate is a multi-machine enterprise pilot plus independent penetration testing before any public Internet exposure.

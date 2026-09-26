# FluxWave Enterprise Test Plan

## Release gate

A build is a release candidate only when all mandatory functional, security, reliability, and performance gates pass.

| Area | Test | Gate |
|---|---|---|
| Integrity | SHA-256 chunk verification | 100% pass |
| Resume | Kill/restart transfer with partial chunks | no valid chunk retransmitted |
| Recovery | Corrupt/fail one peer | successful recovery from another peer |
| TLS | TLS 1.2+ handshake and certificate validation | pass |
| Authentication | missing/wrong/correct bearer token | reject/reject/accept |
| Authorization | peer restricted to configured share root | no escape |
| Traversal | `../`, encoded traversal, malformed chunk names | reject |
| Resource limits | huge manifest / excessive connections | bounded failure |
| Dependencies | pip-audit | no known high/critical vulnerability |
| Static analysis | Bandit | no high-severity finding |
| Performance | 128 MiB baseline | benchmark recorded |
| Scale | 1/4/8/16 GiB test files | integrity pass; throughput recorded |
| Network | 1/10/50/100 ms RTT; packet loss scenarios | recovery and throughput recorded |
| Multi-peer | 1/2/4/8 peers | compare against single-peer baseline |

## Enterprise pilot topology

Use at least three physical or virtual machines:

~~~text
              corporate test network
                      |
        +-------------+-------------+
        |             |             |
     sender-A      sender-B      receiver
     TLS peer      TLS peer       client
        |             |             |
        +-------------+-------------+
                      |
                  firewall ACL
~~~

The receiver must validate certificates, authenticate peers, and reconstruct a file only after every required chunk passes integrity verification.

## Adversarial tests

1. Send requests without Authorization.
2. Send an incorrect bearer token.
3. Send an extremely long Authorization header.
4. Request `../manifest.json` and encoded traversal variants.
5. Request non-numeric and oversized chunk names.
6. Provide a manifest with more than the configured chunk limit.
7. Kill a peer while chunks are in flight.
8. Corrupt a chunk after the manifest has been obtained.
9. Repeatedly open idle connections until the connection limit is reached.
10. Attempt TLS downgrade or certificate-validation bypass in the normal client path.
11. Place credentials in a peer URL and verify that the client refuses them.
12. Run the service using an account that has no permission to unrelated filesystem paths.

## Benchmark methodology

Record:

- file size;
- chunk size;
- number of peers;
- worker count;
- RTT and packet loss;
- CPU and memory usage;
- disk type and filesystem;
- elapsed transfer time;
- effective Mbps;
- retransmitted chunks;
- failed chunks;
- final SHA-256.

Never report a speedup without a baseline run on the same hardware and network conditions.

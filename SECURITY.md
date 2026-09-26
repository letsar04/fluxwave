# FluxWave Security Policy

## Security posture

FluxWave handles potentially sensitive large files. Security is therefore a release gate, not an optional feature.

The project follows a risk-based secure-development approach informed by NIST SSDF and OWASP ASVS. The current implementation is an enterprise-testable LAN prototype, not a claim of certification or production security compliance.

## Required production controls

1. **TLS is mandatory for enterprise deployment.** Use TLS 1.2 or newer and certificate validation. Do not use `--insecure` outside isolated tests.
2. **Peer authentication is mandatory.** Configure a strong bearer token through `FLUXWAVE_AUTH_TOKEN` or an auth-token file. Never put credentials in a peer URL or source code.
3. **Network segmentation is mandatory.** Restrict peer ports with host firewalls/security groups and expose them only to trusted transfer networks.
4. **Least privilege.** Run the peer under an OS account that can read only the directory containing files intended for sharing.
5. **Do not expose the development HTTP mode to the Internet.** `--insecure-http` is for isolated development only.
6. **Protect keys and tokens.** Private keys and token files must be readable only by the service account.
7. **Keep dependencies patched.** CI runs dependency and static security checks before release.
8. **Verify downloaded content.** SHA-256 verification occurs before a downloaded chunk replaces its destination file.

## Threat model

### Assets

- file contents;
- file metadata and manifests;
- peer identity and authorization tokens;
- TLS private keys;
- availability of transfer services.

### Threats addressed

- passive network interception: mitigated by TLS;
- unauthorized peer access: mitigated by bearer authentication and network controls;
- path traversal: rejected at the client and constrained at the server filesystem boundary;
- corrupted chunks: rejected by SHA-256 verification;
- malicious manifest exhaustion: manifest chunk count is bounded;
- connection/resource exhaustion: connection concurrency and socket timeouts are bounded;
- credential leakage through URLs: credentials in URLs are rejected;
- accidental public exposure: CLI binds to loopback by default and refuses plaintext HTTP unless explicitly overridden.

### Residual risks

- bearer tokens are not a substitute for mutual TLS or a full identity system;
- a compromised peer with valid credentials can read all files authorized for that peer;
- discovery traffic is not itself an authenticated trust mechanism;
- SHA-256 provides integrity, not confidentiality or sender authenticity;
- the current protocol does not yet provide signed manifests or end-to-end sender signatures;
- there is no complete multi-tenant authorization model yet;
- denial-of-service resistance is limited and requires network-layer controls.

## Security testing gates

Every release candidate must pass:

- unit and integration tests;
- TLS handshake tests;
- authentication rejection/acceptance tests;
- path traversal regression tests;
- dependency vulnerability audit;
- static security analysis;
- large-file integrity/reconstruction tests;
- failure/retry tests;
- benchmark regression tests.

## Responsible disclosure

Do not publish a working exploit for an unpatched FluxWave vulnerability in a public issue. Report security-sensitive findings privately to the project maintainer through the repository owner’s established GitHub security contact mechanism. Include affected version, impact, reproduction steps, and a minimal proof of concept where safe.

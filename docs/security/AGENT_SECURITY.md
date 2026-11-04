# KRAVIGIL Agent Security

## Trust model

An agent is enrolled by an authenticated KRAVIGIL administrator. The control plane stores the agent's certificate fingerprint and public key. The fingerprint is an identifier, not a credential: possession of the matching private key is required for heartbeat, task polling, and task-result submission.

## Enrollment

The agent runner requires an administrator access token in `KRAVIGIL_ADMIN_TOKEN`. Supply it through the deployment's secret manager or protected environment; do not commit it to source control or bake it into an image.

The agent creates its key and self-signed certificate under `/etc/kravigil/agent` by default. Persist this directory across restarts. The private key is written with owner-only permissions (`0600`). Existing key/certificate pairs are reused; an incomplete or mismatched pair causes startup to fail closed instead of silently changing the enrolled identity.

If an agent identity must be replaced, revoke the old agent in KRAVIGIL and enroll the newly generated identity with an administrator token.

## Signed agent requests

The agent signs each heartbeat, task poll, and task submission using RSA-SHA256. The signed canonical message contains, in order:

1. HTTP method in uppercase
2. Exact request path and query string
3. Unix timestamp in seconds
4. SHA-256 digest of the exact request body

The fields are separated by newline characters. The request carries `X-Agent-Fingerprint`, `X-Agent-Timestamp`, and URL-safe-base64 `X-Agent-Signature` headers. The server verifies the signature against the enrolled public key and rejects missing, invalid, weak-key, revoked-agent, or stale (>5-minute clock skew) requests.

Keep agent and control-plane clocks synchronized. The timestamp window limits the usefulness of captured requests; it is not a substitute for transport encryption or a distributed nonce/replay store.

## Transport and operations

- Use HTTPS for every non-local control-plane connection. The agent client refuses remote plain-HTTP URLs.
- Keep `/etc/kravigil/agent/agent.key` private and backed up only through an approved secrets process.
- Restrict administrator enrollment tokens to the enrollment operation and rotate them according to the organization's credential policy.
- Revoke compromised or retired agents by setting their server-side status to `REVOKED`; signed requests from revoked agents are rejected.
- Monitor heartbeat freshness and investigate repeated signature failures, expired timestamps, and unknown fingerprints.
- Do not expose agent endpoints directly to the public internet without TLS termination, network controls, rate limiting, and monitoring.

## Security boundaries

Signed requests establish proof of possession of the enrolled private key and integrity of the method, path, timestamp, and body. They do not encrypt traffic. HTTPS is mandatory outside local development. The agent's reported IP address is informational and must not be treated as an independently verified network identity.

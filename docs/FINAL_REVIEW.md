# KRAVIGIL — Release Readiness Review

**Assessment date:** 2026-11-04  
**Decision:** **NO-GO — not certified for production deployment**

## Current repository state

- Repository: https://github.com/mohamedelghazali/KRAVIGIL
- Main SHA at the start of this review update: `f08fc74e0bae8f50dabcfc77fa6bc23afb82a2a5`
- Issue #1 inventory: **87/87 entries dispositioned** — 25 implemented with tests or active integration, 62 safely de-scoped, 0 unassigned scaffold entries.
- The inventory count closes the placeholder audit; it is not a production-readiness certification.
- Transport-level mTLS is implemented for the C++ gRPC engine. Backend and worker use distinct client identities; the server verifies client certificates and retains the per-request engine token.
- Production storage no longer relies on a same-host MinIO replica. The deploy script requires an external HTTPS S3-compatible replication target and refuses local/placeholder endpoints. However, the primary evidence store still uses the self-hosted MinIO service; its long-term support/image lifecycle and migration to a managed provider are not resolved. The external replica is not a substitute for selecting and validating a supported primary storage provider.

## Changes already merged

- PRs #19–#24: worker/AI/web-scanner scaffold disposition, reporting data-path correction and reporting tests.
- PR #25: CI now invokes unit, integration, regression and security suites; network scan integration coverage was repaired.
- PR #26: false-positive disposition is preserved across repeated finding correlation.
- PR #27: removed the marker-only performance test; real load/latency benchmarking remains an acceptance requirement.
- PR #28: removed four unused AI-security placeholders in favor of the active Gemini gateway path.
- PR #29: added transport-level gRPC mTLS, distinct backend/worker identities and deployment certificate-chain validation.
- PR #30: hardened AI evidence sanitization/output validation and removed duplicate tenant/scope/prompt-guard placeholders.
- PR #33: removed same-host target MinIO from the production overlay; added an off-host HTTPS replication target and a dual-network replication runner.
- PR #35: added Alembic revision `0008_scan_task_id`, fixed the tested “ignore the above rules” prompt-injection variant, and replaced static fake secret fixtures that triggered Gitleaks.

## Validation evidence and remaining gaps

### Backend and application CI

The most recent full backend run before PR #35 (run `41861082647`) reported **134 passed, 2 failed**:
1. PostgreSQL regression exposed the missing `scans.task_id` migration.
2. Prompt-injection coverage exposed the “ignore the above rules” wording variant.

Both code fixes are now merged in PR #35. **A fresh complete run on the post-PR-35 main SHA is still required**; the earlier run cannot be retroactively treated as passing.

### Security and build evidence

- PR #29: lint/type checks, frontend build, C++ build, security scans, and backend/network-engine/worker image builds passed. Its backend job still failed on the then-missing migration.
- PR #30: the Gitleaks scan flagged static test-only token examples; PR #35 replaced those literals with dynamically constructed fixtures. A fresh Gitleaks run on the current main SHA is still required.
- PR #33: Ruff/MyPy, frontend and C++ jobs passed; Python security and secret scanning passed. Its Compose validation failed because the CI command did not explicitly load `.env.example`. Backend tests had the two failures listed above. The backend and network-engine images passed; the worker image was still running at the last recorded check.
- The current CI correction uses `docker compose --env-file .env.example` and syntax-checks the production deployment/replication scripts. It must pass in a fresh run before this document can be upgraded.

### Production acceptance — not executed

1. Select and contract a supported primary S3-compatible provider and a separate replication target that supports the MinIO Client replication and lifecycle APIs; configure a separate account/region/failure domain. The current primary still runs self-hosted MinIO and is not certified for long-term production support.
2. Define evidence and backup retention, Object Lock/immutability, legal deletion semantics, RPO and RTO. Evidence delete markers are replicated; backup-bucket deletions are intentionally not propagated.
3. Execute a real object replication test and verify content hashes on the remote target.
4. Execute an encrypted PostgreSQL backup and an isolated restore drill; verify the restored database and evidence objects.
5. Deploy to a production-like staging host with real DNS, HTTPS certificate renewal, mTLS certificates, secret rotation, non-superuser database role, monitoring, alerting and runbooks.
6. Run representative load, latency, worker-recovery and resource-exhaustion tests. The former placeholder benchmark was removed; no performance acceptance result is claimed.
7. Verify tenant isolation across API, worker and storage paths using PostgreSQL RLS and non-superuser runtime credentials.
8. Make frontend builds reproducible: `frontend/package.json` currently has caret ranges and no npm lockfile, so CI uses `npm install` rather than `npm ci`. Generate and commit `package-lock.json`, then switch CI to `npm ci`.
9. Pin production container images and GitHub Actions to immutable versions/digests. The Compose stack still contains floating tags such as `minio/minio:latest`, `postgres:15-alpine`, and `redis:7-alpine`; do not treat mutable tags as a supply-chain lock.

## Release gate

Do not declare the project production-ready or expose it to public users until one exact candidate SHA passes all required CI, security, Compose and three-image gates, and every production acceptance item above has verifiable evidence.

The current deployment script deliberately fails until a real remote HTTPS replication endpoint and credentials are configured. No production deployment has been performed from this review.

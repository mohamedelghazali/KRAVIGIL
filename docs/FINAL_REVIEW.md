# KRAVIGIL — Release Readiness Review
**Assessment date:** 2026-11-04  
**Status:** NOT RELEASE CERTIFIED

> This assessment supersedes earlier statements that KRAVIGIL was complete or production-ready. Repository presence, successful static checks, and a successful container build do not establish feature completeness or production acceptance.

## Verified engineering work

- Alembic migration heads were merged with a graph-only merge revision (\`0006_merge_rls_heads\`).
- SQLAlchemy UUID columns use the cross-dialect \`Uuid\` type so SQLite test fixtures and PostgreSQL deployments share the same model definitions.
- Scan and Observation ORM relationships are bidirectional.
- JWT subject values are parsed and validated as UUIDs before querying user records.
- Password hashing dependency is pinned to a Passlib-compatible bcrypt release.
- gRPC Python bindings are generated in CI and have checked-in type declarations.
- Network engine cancellation ordering, timer cancellation, and port-range validation were corrected.
- CI now exercises PostgreSQL migrations and tenant RLS using a non-superuser application role.
- Evidence integration tests use a pinned S3-compatible test server; this is a test double, not a production object store.

## CI checks

The latest CI runs must be inspected directly before each release decision. The following checks have passed in recent runs:

- Ruff
- MyPy
- Frontend build
- C++ network engine compilation and unit tests
- Gitleaks secret scan
- Bandit high-severity scan
- pip-audit dependency scan

Black formatting is currently non-blocking. The latest check reported **84 files would be reformatted**; this is outstanding formatting debt, not a passing formatting check.

**Latest verified application commit:** `0a99199a` (2026-11-03).

The main CI workflow passed on that commit:
- Backend/security tests: **19 passed**, PostgreSQL migrations and RLS included; measured coverage **59%**.
- Ruff and MyPy: passed.
- Frontend production build: passed.
- C++ network engine build and unit tests: passed.
- Backend and network-engine container builds in the main CI workflow: passed.

The separate Docker verification workflow was hardened after the earlier run was cancelled: image builds now run as three independent matrix jobs (backend, worker, network engine), `fail-fast` is disabled, in-flight runs are not cancelled by newer pushes, and each job has a 60-minute timeout. The hardened workflow was triggered on review commit `8203fca64edb5d411a2e27e9226776516477dd55` (run [41731335426](https://github.com/mohamedelghazali/KRAVIGIL/actions/runs/41731335426)). At the time of this review it was still pending and had not exposed its matrix jobs; no image-build result is claimed until backend, worker, and network-engine jobs all complete.

## Release blockers

### 1. Incomplete implementation

The original inventory contained **87 Python source files** with the explicit scaffold marker. Eight inventory entries (shared severity/status enums and asset/evidence/finding/report/scan/user schemas) now have implementations and focused unit tests; **79 entries remain open**. The schema-focused backend suite passed in PR #5 CI (85 tests total, 61% measured repository coverage); broader end-to-end acceptance remains outstanding. The remaining files carry the marker:

\`KRAVIGIL module scaffold. Implementation pending.\`

These are not functional implementations. Each must either be implemented and tested against an acceptance criterion, or formally removed from the shipped scope. A placeholder must never be counted as a completed module. A blocking inventory and closure checklist is tracked in [issue #1](https://github.com/mohamedelghazali/KRAVIGIL/issues/1).

### 2. Production object storage

The production Compose configuration and replication scripts still depend on the upstream \`minio/minio\` and \`minio/mc\` images. The upstream community image distribution has changed; the CI S3Mock service is only for tests and cannot replace production storage.

Before production deployment, select and configure a supported S3-compatible provider with verified versioning, replication, retention/Object Lock requirements, backup access, TLS, and restore behavior. Update Compose, backup, replication, environment examples, and operations documentation together. Do not deploy against S3Mock.

### 3. Production acceptance not executed

No production deployment has been performed from this review. The following remain unverified on a real deployment target:

- HTTPS ingress, certificate renewal, and externally reachable health checks
- Secret injection and rotation
- Complete application startup and service health
- Tenant isolation across all API and worker paths
- Evidence retention, integrity verification, and cross-location replication
- Encrypted backup creation and isolated restore drill
- Worker queue recovery and retry behavior
- Monitoring, alert delivery, and incident response runbooks
- Resource limits and load behavior under concurrent scans

### 4. Quality and maintenance debt

- Black reports 84 files requiring formatting.
- Frontend CI currently uses \`npm install\` because a lockfile is absent; generate and commit a reviewed lockfile, then return CI to \`npm ci\`.
- Pydantic v1-style validators and class-based configuration still generate deprecation warnings.
- Add meaningful coverage thresholds only after the unimplemented modules have tests; current test success alone is not a coverage guarantee.

## Release decision

**NO-GO.** KRAVIGIL is not certified for production release until the remaining scaffold inventory in [issue #1](https://github.com/mohamedelghazali/KRAVIGIL/issues/1) is resolved, the current candidate PR #4 passes all required checks on one commit, backend and all three container-image workflows pass on the same commit, production object storage is migrated/configured and verified, and an isolated backup/restore acceptance run succeeds.

## 2026-11-04 closure update

- PR #2 was merged to `main` (merge commit `9e59954fb999ee4f60b3dc58e1d835ed31c4397d`), adding the evidence-based closure plan and full-history Gitleaks checkout.
- Implemented shared severity/status enums and scan/finding Pydantic schemas, with focused unit tests. The four corresponding issue #1 inventory entries are checked as implemented; CI and integration acceptance are still required.
- PR #4 (`feat(api): close scan and finding schema scaffold slice`) was merged. Its backend test job failed (75 passed, 1 failed) because uppercase `RESOLVED` did not normalize; this was corrected on `main` with regression coverage. PR #5 integrates the asset, user, and report schemas into their API endpoints and is undergoing CI revalidation.
- Latest recorded closure-plan commit: `610d83fafc15744f470037d13eab3a121c68c626`. This is a documentation commit, not evidence that all tests passed.
- PR #4's frontend, C++ build, lint, container-build job, Bandit, pip-audit, and Gitleaks checks passed; its backend test job failed. PR #9's CI/security/image gates passed. PR #11 de-scopes six unused integration scaffolds; its backend tests and security checks passed, while C++/container/image checks remain in progress. No production acceptance or release approval is claimed.

A green CI run is necessary but not sufficient. Reassess this document after every blocker is closed and attach the exact commit SHA and workflow run URLs to the release record.

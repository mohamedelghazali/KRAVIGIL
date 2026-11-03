# KRAVIGIL — Release Readiness Review
**Assessment date:** 2026-11-03  
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

Backend tests have exposed and driven fixes for model mappings, UUID handling, test credentials, password hashing compatibility, risk-score expectations, and S3 test infrastructure. Do not mark backend acceptance complete until the latest full test job passes.

## Release blockers

### 1. Incomplete implementation

The repository contains **87 Python source files** that are explicit scaffolds with the marker:

\`KRAVIGIL module scaffold. Implementation pending.\`

These are not functional implementations. Each must either be implemented and tested against an acceptance criterion, or formally removed from the shipped scope. A placeholder must never be counted as a completed module.

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

**NO-GO.** KRAVIGIL is not certified for production release until the scaffold inventory is resolved, backend and container workflows pass on the same commit, production object storage is migrated/configured and verified, and an isolated backup/restore acceptance run succeeds.

A green CI run is necessary but not sufficient. Reassess this document after every blocker is closed and attach the exact commit SHA and workflow run URLs to the release record.

# KRAVIGIL Release Process

This document describes the repository's current tag-triggered release workflow. A release build is not a production deployment.

## 1. Release trigger

The workflow in `.github/workflows/release.yml` runs when a version tag matching `v*.*.*` is pushed (for example, `v1.2.3`).

Before creating a tag:

1. Review the candidate commit and confirm it is the intended `main` release point.
2. Confirm the required GitHub workflows pass on that exact commit: **KRAVIGIL CI**, **Security Scans**, and **Docker Image Build Verification**.
3. Confirm the release decision and outstanding operational gates in [the Engineering Work Register](../engineering/WORK_REGISTER.md). Do not interpret CI success as Staging, restore, performance, or production acceptance.
4. Review the [Production Deployment Guide](../deployment/PRODUCTION.md) and applicable release notes.

## 2. Tag-triggered validation and publication

The release workflow validates Python compilation, database migrations against its PostgreSQL service, backend/security tests, Bandit, pip-audit, C++ build/tests, and the frontend dependency install/build.

After validation succeeds, the workflow builds and pushes five images to GitHub Container Registry:

- `kravigil-backend`
- `kravigil-worker`
- `kravigil-network-engine`
- `kravigil-frontend`
- `kravigil-backup`

The published image tag is the pushed Git tag (for example, `v1.2.3`). Verify the workflow result and all five package artifacts before treating image publication as complete.

## 3. Deployment is a separate operation

The release workflow does **not** deploy to Staging or Production. Deploy only through the reviewed environment-specific process:

- Staging: [Staging Acceptance Runbook](STAGING_ACCEPTANCE.md)
- Production: [Production Deployment Guide](../deployment/PRODUCTION.md)

Use pinned image digests and environment-specific secrets when promoting artifacts. Never promote a build solely because a tag exists.

## 4. Evidence and release decision

Record the tag, source commit SHA, workflow run URL, validation result, and image digests in the release record. Preserve failed runs and remediation history.

The release remains **NO-GO for production** until Staging acceptance, off-host restore, approved performance objectives, storage/recovery decisions, final security review, and repository governance requirements are satisfied with evidence.

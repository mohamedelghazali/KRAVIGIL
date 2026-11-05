# KRAVIGIL Engineering Work Register

**Purpose:** Single source of truth for release work, issue closure, and regression prevention.  
**Last reconciled:** 2026-11-05  
**Current main SHA at start of this release-readiness slice:** `f2926554e1ea0c58befa3b8c60c698e3176de3ea` (PR #69 merge commit; this slice is under verification)  
**Release decision:** **NO-GO for production** until every applicable release gate below has evidence.

This register supplements the historical [Release Closure Execution Plan](../RELEASE_CLOSURE_PLAN.md). If historical notes conflict with this register, use the latest dated, SHA-specific entry here and preserve the historical log for auditability.

## 1. Non-negotiable change-control rules

1. **One canonical work item per root cause.** Before creating a task, search this register and linked GitHub issues/PRs for the same failure signature, component, and acceptance criterion.
2. **No duplicate repair.** If an item is already `IN_PROGRESS`, continue its existing branch/PR. If `VERIFIED` or `CLOSED`, do not reopen it unless new evidence demonstrates regression.
3. **Evidence before closure.** A work item is `VERIFIED` only when the exact tested commit SHA, focused test result, and applicable workflow run URLs are recorded.
4. **Separate root causes.** A new failure discovered after a repair gets a new child item linked to the parent; do not rewrite the original issue or mark the original repair as failed unless its own acceptance test regressed.
5. **One coherent PR per root cause or tightly coupled slice.** Avoid unrelated formatting, dependency, security, and functional changes in one PR.
6. **No merge on pending, failed, or missing required checks.** A green run on another SHA is not evidence for the candidate SHA.
7. **Do not repeat expensive suites manually after every edit.** Run focused tests during iteration; run the full required CI matrix once the PR candidate is ready. GitHub-required workflows remain authoritative.
8. **No false closure.** A code change, unit test, successful build, or deployment script does not prove live deployment, tenant isolation, backup recoverability, or production readiness.
9. **Record external blockers explicitly.** Provider selection, credentials, staging infrastructure, data residency, retention, and RPO/RTO remain blocked until evidence and an accountable decision exist.
10. **Never erase history.** Append dated reconciliation notes; do not silently replace prior evidence or historical counts.

## 2. Work-item lifecycle

| State | Meaning | Permitted next action |
|---|---|---|
| `OPEN` | Known gap, no active implementation | Scope and assign one implementation path |
| `IN_PROGRESS` | One branch/PR owns the root cause | Continue that branch/PR; no duplicate |
| `BLOCKED` | External decision, credential, or infrastructure required | Record exact blocker and evidence needed |
| `READY_FOR_VERIFY` | Implementation complete; focused checks passed | Run full required workflows on candidate SHA |
| `VERIFIED` | Acceptance criteria passed on exact SHA | Mark complete; reopen only on regression evidence |
| `CLOSED` | Merged and evidence retained | Do not repeat; monitor for regression |

A work item must include: ID, symptom/root cause, owner branch/PR, affected component, acceptance criteria, focused test, full workflow evidence, exact verified SHA, dependencies, and closure date.

## 3. Current release work register

| ID | Workstream | State | Canonical evidence / next action |
|---|---|---|---|
| KV-001 | Scan dispatch failure persistence (network/web/cloud/SAST) | CLOSED | PRs #53 and #60 merged; regression tests verify persisted FAILED state and error metadata. |
| KV-002 | Evidence upload/delete failure consistency | CLOSED | PRs #54 and #59 merged; tests cover post-commit refresh failure, DB commit failure, ambiguous upload cleanup, and retryable tombstones. |
| KV-003 | Scheduled scan scheduler process | IN_PROGRESS — deployment orchestration fix | PR #61 added the Beat service, but the production deployment script did not include it in the application startup command. Current release-readiness PR adds scheduler startup and regression coverage; runtime ticks still require staging evidence under KV-008. |
| KV-004 | Automatic retry of pending Evidence deletion tombstones | CLOSED — code/CI | PR #62 introduced tenant-scoped periodic reconciliation; PR #63 fixed its MyPy typing failure and merged as `528401ac4c6b4da6d57710ba676213f45264afdb`. All three required workflows passed on PR #63 head. Runtime operation is verified separately under KV-008. |
| KV-005 | Tenant isolation across API and PostgreSQL RLS | CLOSED — code/CI | PR #66 merged as `2a03b26c9d043daa19519cfff992b705bac78c00`; tested head `8a35d8faafd20a948d3c7cf562520b1b1efe359d`. PostgreSQL RLS integration tests executed (not skipped); 183 backend tests passed. CI `42053405547`, Security `42053405775`, Docker `42053405413` all passed on the exact tested head. API test coverage still includes SQLite; live staging acceptance remains KV-008. |
| KV-006 | Reproducible frontend dependency install | CLOSED — code/CI | PR #67 merged as `36c9c16f5d369e034df7c9e14f80da789042cce7`; tested head `cd53ada111dd0b70eae6c0d1caa0095e74af8cd6`. npm-generated v3 lockfile (111 package entries); CI/release/Docker use `npm ci`; frontend Docker build aligned to Node 20. CI `42060470533`, Security `42060470450`, Docker `42060470492` all passed on exact head. Runtime deployment acceptance remains KV-008. |
| KV-007 | Backup and restore validation | BLOCKED — operational | Scripts and runbook exist. A real isolated restore from the off-host replica, including evidence object hash checks and application smoke tests, has not been evidenced. Requires authorized staging/recovery infrastructure and independently escrowed key. |
| KV-008 | Staging deployment and runtime acceptance | BLOCKED — operational | No verified live staging deployment evidence is recorded. Validate scheduler ticks, worker execution, database, Redis, MinIO/S3, health, auth/MFA, scan/report/evidence workflows, logs and alerts. |
| KV-009 | Performance and capacity acceptance | IN_PROGRESS — implementation merged | PR #69 merged as `f2926554e1ea0c58befa3b8c60c698e3176de3ea`; exact tested head `333126231bedbbe89c82fdaf67b3d7512b84ad4f`. Focused runner tests, CI `42068905894`, Security `42068905643`, and Docker `42068905375` all passed. Representative staging load, resource/queue/storage telemetry, and approved SLO acceptance remain outstanding. |
| KV-010 | Production storage and recovery decisions | BLOCKED — decision | Select provider and document TLS, IAM, residency, replication, retention/Object Lock, backup target, RPO/RTO, cost, and recovery ownership. Do not infer these choices from Compose defaults. |
| KV-011 | Release security review | DEFERRED — final phase | Run comprehensive threat-model and security review after functional, tenant, staging, recovery and performance gates are closed. Routine CI security scans remain mandatory throughout. |
| KV-012 | Branch protection / merge governance | OPEN — repository setting | Verify required checks and review rules on `main`. Configuration must be changed in repository settings by an authorized maintainer; code changes cannot substitute for this setting. |

## 4. PR #63 — closed with exact-head evidence

**PR:** [#63 — Resolve Evidence reconciler MyPy failure](https://github.com/mohamedelghazali/KRAVIGIL/pull/63)  
**Tested head SHA:** `09759a6d91a7f1a0dbf4158c684f0914625fdc46`  
**Merge commit:** `528401ac4c6b4da6d57710ba676213f45264afdb`

| Workflow | Run ID | Final result |
|---|---:|---|
| KRAVIGIL CI | `42046894751` | Passed — backend, C++, frontend, lint/type checks, container build |
| Security Scans | `42046894774` | Passed |
| Docker Image Build Verification | `42046894683` | Passed — backend, worker, network-engine images |

PR #63 was merged only after all three workflows completed successfully and the head SHA was rechecked. The original MyPy failure is closed; do not repeat this repair unless the same type error demonstrably returns.

## 4.1 Documentation work-register PR

**PR:** [#65 — Establish canonical engineering work register](https://github.com/mohamedelghazali/KRAVIGIL/pull/65)  
**Tested head SHA:** `9e7a7a68f7b68c41b319c65ba167cf0bcac4f36d`  
**Merge commit:** `1d678d8922a2baae1529555f9c71913f41dc6e30`

| Workflow | Run ID | Final result |
|---|---:|---|
| KRAVIGIL CI | `42048718233` | Passed |
| Security Scans | `42048718320` | Passed |
| Docker Image Build Verification | `42048718160` | Passed |

PR #65 is merged. The prior main SHA and PR #63 evidence remain preserved above.

## 4.2 Superseded documentation PR

**PR:** [#64 — Establish canonical engineering work register](https://github.com/mohamedelghazali/KRAVIGIL/pull/64)  
Closed without merge because its branch was based on the pre-squash PR #63 history and had diverged from current main. It must not be reopened; PR #65 is the clean merged replacement.

## 4.3 Tenant-isolation verification

**Owner PR:** [#66 — Verify PostgreSQL RLS and worker tenant context](https://github.com/mohamedelghazali/KRAVIGIL/pull/66)  
**Branch:** `fix/tenant-rls-worker-isolation-2026-11-05`  
**Base SHA:** `1d678d8922a2baae1529555f9c71913f41dc6e30`

PR #66 merged successfully. Its PostgreSQL integration tests verified the restricted application role, ENABLE/FORCE RLS, cross-tenant read/write/update/delete isolation, and Celery worker tenant-context cleanup on a reused pooled connection. The two new RLS/worker tests executed rather than skipped; the backend suite reported 183 passed. All required workflows passed on the exact tested head SHA `8a35d8faafd20a948d3c7cf562520b1b1efe359d`:

| Workflow | Run ID | Final result |
|---|---:|---|
| KRAVIGIL CI | `42053405547` | Passed |
| Security Scans | `42053405775` | Passed |
| Docker Image Build Verification | `42053405413` | Passed |

**Merge commit:** `2a03b26c9d043daa19519cfff992b705bac78c00`. KV-005 is closed for code/CI evidence. Live staging acceptance remains tracked separately under KV-008.

## 5. Release decision rules

Production release is **GO** only when all applicable conditions are true on a reviewed candidate:

- [ ] Required CI, backend tests, migrations, RLS, lint/type checks, frontend build, C++ tests, security scans, and all production images pass on the candidate SHA.
- [x] Frontend dependency installation is deterministic and lockfile-backed (KV-006; PR #67).
- [ ] Tenant isolation is demonstrated for API, direct database RLS using the restricted application role, and asynchronous workers.
- [ ] Staging deployment is healthy and scheduled scans demonstrably execute.
- [ ] A real off-host encrypted backup restore succeeds in an isolated environment; restored DB and evidence objects pass integrity checks.
- [ ] Performance/load tests meet explicitly approved service objectives.
- [ ] Production object-storage, TLS, IAM, retention, replication, residency, RPO/RTO, monitoring, and incident/recovery ownership are documented and verified.
- [ ] Final security review is complete and findings are closed or formally risk-accepted.
- [ ] Main branch protection and required status checks are verified.
- [ ] Final review records the exact release SHA and links every evidence artifact.

Until then, keep the release **NO-GO**. This is not a judgement that development is unusable; it is a distinction between merged engineering improvements and verified production operations.

## 6. Reconciliation procedure for every future session

1. Read this register first.
2. Read the current `main` SHA and open PRs; compare them with each work-item owner.
3. Inspect only work items that are `OPEN`, `IN_PROGRESS`, `BLOCKED`, or have new regression evidence.
4. Reuse an existing branch/PR when the same root cause is already active.
5. Update the register in the same PR as a material status transition; include SHA and workflow IDs.
6. Do not rerun completed workstreams unless the candidate SHA changes, a required workflow is missing, or a regression is demonstrated.
7. End each work session with: completed IDs, still-open IDs, blockers, exact current SHA, and the next single work item.

This process is designed to make progress cumulative and auditable, not to eliminate required CI runs when code changes.


## 4.4 Frontend reproducible dependency installation — in progress

**Owner PR:** [#67 — Make frontend dependency installation reproducible](https://github.com/mohamedelghazali/KRAVIGIL/pull/67)  
**Branch:** `fix/frontend-reproducible-install-2026-11-05`  
**Generation workflow:** [Run 42059936652](https://github.com/mohamedelghazali/KRAVIGIL/actions/runs/42059936652) — completed successfully on GitHub Actions using Node 20 and the public npm registry. The lockfile was generated by npm, not authored manually.  
**Generated lockfile:** `frontend/package-lock.json`, lockfileVersion 3, 111 package entries.  
**Implementation:** CI and release validation use `npm ci`; `frontend/Dockerfile` uses `node:20-alpine` and `npm ci`. The temporary lockfile-generation workflow is removed from the PR branch.  
**Acceptance:** clean `npm ci` plus `npm run build` must pass in CI and Docker image build verification on the exact PR head; all required CI, Security, and Docker workflows must pass before merge. KV-006 remains open until those results are recorded and the PR is merged.


## 4.5 Frontend reproducible dependency installation — closed

**Owner PR:** [#67 — Make frontend dependency installation reproducible](https://github.com/mohamedelghazali/KRAVIGIL/pull/67)  
**Tested head SHA:** `cd53ada111dd0b70eae6c0d1caa0095e74af8cd6`  
**Merge commit / current main at closure:** `36c9c16f5d369e034df7c9e14f80da789042cce7`  
**Merged:** 2026-11-05.

The npm lockfile was generated in GitHub Actions run `42059936652` with Node 20 against the public npm registry. It uses lockfileVersion 3 and contains 111 package entries; all 110 resolved tarball URLs use `registry.npmjs.org` and have integrity hashes. CI, release validation, and the frontend Docker image now use `npm ci`; the Docker build stage uses Node 20. The Docker image verification matrix and main CI also build the frontend image.

| Workflow | Run ID | Exact tested head | Result |
|---|---:|---|---|
| KRAVIGIL CI | `42060470533` | `cd53ada111dd0b70eae6c0d1caa0095e74af8cd6` | Passed — backend, C++, frontend, lint/type checks, container build |
| Security Scans | `42060470450` | `cd53ada111dd0b70eae6c0d1caa0095e74af8cd6` | Passed — Python security and secret scan |
| Docker Image Build Verification | `42060470492` | `cd53ada111dd0b70eae6c0d1caa0095e74af8cd6` | Passed — backend, worker, network-engine, frontend images |

KV-006 is closed for code/CI. This does not substitute for live staging/runtime acceptance under KV-008.


## 4.6 Performance and capacity baseline — implementation in progress

**Owner PR:** [#69 — Add a bounded API performance baseline harness](https://github.com/mohamedelghazali/KRAVIGIL/pull/69)  
**Scope:** Read-only API load runner, safe endpoint allowlist, JSON latency/error/throughput report, focused validation tests, and performance acceptance runbook.

The harness is intentionally bounded to `/health`, `/api/v1/system/version`, and authenticated tenant-scoped `/api/v1/targets/` GET requests. It rejects mutating routes and remote plain HTTP, requires a bearer token for tenant data, does not retry, and caps request rate at 15/s. The provisional p95/error thresholds are smoke checks, not approved service SLOs.

**Not yet evidenced:** representative staging load, p95/p99 under realistic workload, worker/queue saturation, database and object-storage capacity, host/container resource utilization, or recovery under load. KV-009 remains open until those operational measurements and approved SLOs exist.


## 4.7 Release-readiness corrections — in progress

**Owner branch:** `fix/production-release-scheduler-and-frontend-image-2026-11-05`  
**Base SHA:** `f2926554e1ea0c58befa3b8c60c698e3176de3ea`

A final deployment-path review found two release defects: the production deployment script did not start the configured Celery Beat scheduler, and the tag-triggered release pipeline omitted the frontend and backup service images, and the Docker verification matrix did not build the backup image. This change starts the scheduler in the production rollout, adds the frontend and backup images to Docker verification, publishes all five runtime images to GHCR on version tags, and adds regression tests for these contracts. KV-003 remains pending until this change passes exact-head CI and the scheduler is observed executing in staging. Release-image publication is not production deployment by itself.

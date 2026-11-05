# KRAVIGIL Engineering Work Register

**Purpose:** Single source of truth for release work, issue closure, and regression prevention.  
**Last reconciled:** 2026-11-05  
**Baseline under review:** `09759a6d91a7f1a0dbf4158c684f0914625fdc46` (PR #63 head)  
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
| KV-003 | Scheduled scan scheduler process | CLOSED — code/CI | PR #61 merged; scheduler service configured with one production replica. Runtime scheduling still requires staging evidence under KV-008. |
| KV-004 | Automatic retry of pending Evidence deletion tombstones | IN_PROGRESS | PR #62 introduced tenant-scoped periodic reconciliation. PR #63 fixes its MyPy typing failure; do not create a second reconciler. Finish PR #63 validation and merge only when all exact-head required checks pass. |
| KV-005 | Tenant isolation across API and PostgreSQL RLS | OPEN / PARTIAL | Existing API tenant-isolation tests and PostgreSQL RLS integration test are present. Confirm the RLS test actually executes (not skipped), expand worker/task tenant-boundary coverage, and retain exact CI evidence. |
| KV-006 | Reproducible frontend dependency install | OPEN | `frontend/package-lock.json` is absent; CI currently uses `npm install`. Generate and verify the lockfile in a network-enabled CI environment, then switch to `npm ci` in a dedicated PR. Never hand-author a lockfile. |
| KV-007 | Backup and restore validation | BLOCKED — operational | Scripts and runbook exist. A real isolated restore from the off-host replica, including evidence object hash checks and application smoke tests, has not been evidenced. Requires authorized staging/recovery infrastructure and independently escrowed key. |
| KV-008 | Staging deployment and runtime acceptance | BLOCKED — operational | No verified live staging deployment evidence is recorded. Validate scheduler ticks, worker execution, database, Redis, MinIO/S3, health, auth/MFA, scan/report/evidence workflows, logs and alerts. |
| KV-009 | Performance and capacity acceptance | OPEN | Define workload profile and SLOs; run API/worker/queue/database/object-storage load tests; record p95/p99 latency, throughput, error rate, resource use and saturation. |
| KV-010 | Production storage and recovery decisions | BLOCKED — decision | Select provider and document TLS, IAM, residency, replication, retention/Object Lock, backup target, RPO/RTO, cost, and recovery ownership. Do not infer these choices from Compose defaults. |
| KV-011 | Release security review | DEFERRED — final phase | Run comprehensive threat-model and security review after functional, tenant, staging, recovery and performance gates are closed. Routine CI security scans remain mandatory throughout. |
| KV-012 | Branch protection / merge governance | OPEN — repository setting | Verify required checks and review rules on `main`. Configuration must be changed in repository settings by an authorized maintainer; code changes cannot substitute for this setting. |

## 4. PR #63 candidate validation

**PR:** [#63 — Resolve Evidence reconciler MyPy failure](https://github.com/mohamedelghazali/KRAVIGIL/pull/63)  
**Head SHA:** `09759a6d91a7f1a0dbf4158c684f0914625fdc46`

| Workflow | Run ID | Observed state at reconciliation |
|---|---:|---|
| KRAVIGIL CI | `42046894751` | In progress; backend, C++, frontend, lint passed; standard container-build job was still building worker image |
| Security Scans | `42046894774` | Passed |
| Docker Image Build Verification | `42046894683` | Passed: backend, worker, network-engine images |

**Merge gate:** Re-fetch PR and all workflows for the exact head SHA. Merge only when every required run is completed successfully and the PR head has not changed. If any check fails, record the failing job/step and create a child item only if it is a distinct root cause.

## 5. Release decision rules

Production release is **GO** only when all applicable conditions are true on a reviewed candidate:

- [ ] Required CI, backend tests, migrations, RLS, lint/type checks, frontend build, C++ tests, security scans, and all production images pass on the candidate SHA.
- [ ] Frontend dependency installation is deterministic and lockfile-backed.
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

# KRAVIGIL Engineering Work Register

**Purpose:** Single source of truth for release work, issue closure, and regression prevention.  
**Last reconciled:** 2026-11-07  
**Current main SHA at reconciliation (2026-11-07):** `31301b893e6744ec77d464ece02646f5abf0735d` (PR #81 merge commit; all three post-merge workflows passed on this exact SHA)  
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
| KV-003 | Scheduled scan scheduler process | CLOSED — code/CI; runtime pending | PR #71 merged as `d12bb9daa67dfb66274006590f41f85dcc30d100`; exact PR head `0dfafe3ad585635dc9242b821fc9697d5dcd4a4b` passed CI, Security, and Docker workflows. Production deployment now starts the scheduler. Actual scheduled ticks still require staging evidence under KV-008. |
| KV-004 | Automatic retry of pending Evidence deletion tombstones | CLOSED — code/CI | PR #62 introduced tenant-scoped periodic reconciliation; PR #63 fixed its MyPy typing failure and merged as `528401ac4c6b4da6d57710ba676213f45264afdb`. All three required workflows passed on PR #63 head. Runtime operation is verified separately under KV-008. |
| KV-005 | Tenant isolation across API and PostgreSQL RLS | CLOSED — code/CI | PR #66 merged as `2a03b26c9d043daa19519cfff992b705bac78c00`; tested head `8a35d8faafd20a948d3c7cf562520b1b1efe359d`. PostgreSQL RLS integration tests executed (not skipped); 183 backend tests passed. CI `42053405547`, Security `42053405775`, Docker `42053405413` all passed on the exact tested head. API test coverage still includes SQLite; live staging acceptance remains KV-008. |
| KV-006 | Reproducible frontend dependency install | CLOSED — code/CI | PR #67 merged as `36c9c16f5d369e034df7c9e14f80da789042cce7`; tested head `cd53ada111dd0b70eae6c0d1caa0095e74af8cd6`. npm-generated v3 lockfile (111 package entries); CI/release/Docker use `npm ci`; frontend Docker build aligned to Node 20. CI `42060470533`, Security `42060470450`, Docker `42060470492` all passed on exact head. Runtime deployment acceptance remains KV-008. |
| KV-007 | Backup and restore validation | BLOCKED — operational | Scripts and runbook exist. A real isolated restore from the off-host replica, including evidence object hash checks and application smoke tests, has not been evidenced. Requires authorized staging/recovery infrastructure and independently escrowed key. |
| KV-008 | Staging deployment and runtime acceptance | BLOCKED — operational | No verified live staging deployment evidence is recorded. Validate scheduler ticks, worker execution, database, Redis, MinIO/S3, health, auth/MFA, scan/report/evidence workflows, logs and alerts. |
| KV-009 | Performance and capacity acceptance | IN_PROGRESS — implementation merged | PR #69 merged as `f2926554e1ea0c58befa3b8c60c698e3176de3ea`; exact tested head `333126231bedbbe89c82fdaf67b3d7512b84ad4f`. Focused runner tests, CI `42068905894`, Security `42068905643`, and Docker `42068905375` all passed. Representative staging load, resource/queue/storage telemetry, and approved SLO acceptance remain outstanding. |
| KV-010 | Production storage and recovery decisions | BLOCKED — decision | Select provider and document TLS, IAM, residency, replication, retention/Object Lock, backup target, RPO/RTO, cost, and recovery ownership. Do not infer these choices from Compose defaults. |
| KV-011 | Release security review | DEFERRED — final phase | Run comprehensive threat-model and security review after functional, tenant, staging, recovery and performance gates are closed. Routine CI security scans remain mandatory throughout. |
| KV-012 | Branch protection / merge governance | OPEN — repository setting | Rechecked after PR #81: the repository rulesets endpoint returns an empty list (`[]`), so no repository rulesets are configured. The branch-protection endpoint returns HTTP 403 to this integration, so the current classic branch-protection details cannot be independently read here. KV-012 remains open until an authorized maintainer configures and verifies `main` protection and required checks. |

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

A final deployment-path review found two release defects: the production deployment script did not start the configured Celery Beat scheduler, and the tag-triggered release pipeline omitted the frontend and backup service images, and the Docker verification matrix did not build the backup image. This change starts the scheduler in the production rollout, adds the frontend and backup images to Docker verification, publishes all five runtime images to GHCR on version tags, and adds regression tests for these contracts. The newly enabled backup-image build exposed a base-image account-name collision; the service account was renamed to `kravigil-backup`, with a regression assertion. The first exact-head CI run also exposed a test-string escaping defect, which was corrected. PR #71 merged as `d12bb9daa67dfb66274006590f41f85dcc30d100` after all three required workflows passed on exact PR head `0dfafe3ad585635dc9242b821fc9697d5dcd4a4b`. The scheduler startup command and five-image release/verification coverage are now merged. KV-003 is closed for code/CI; observing actual scheduler ticks remains an operational acceptance item under KV-008. Release-image publication is not production deployment by itself.


## 4.8 PR #71 release-readiness corrections — merged and CI-verified

**PR:** [#71 — Start scheduler and publish all runtime images](https://github.com/mohamedelghazali/KRAVIGIL/pull/71)  
**Exact tested PR head:** `0dfafe3ad585635dc9242b821fc9697d5dcd4a4b`  
**Merge commit / current main at this reconciliation:** `d12bb9daa67dfb66274006590f41f85dcc30d100`

| Workflow | Run ID | Exact tested head | Result |
|---|---:|---|---|
| KRAVIGIL CI | `42078390410` | `0dfafe3ad585635dc9242b821fc9697d5dcd4a4b` | Passed |
| Security Scans | `42078390497` | `0dfafe3ad585635dc9242b821fc9697d5dcd4a4b` | Passed |
| Docker Image Build Verification | `42078390471` | `0dfafe3ad585635dc9242b821fc9697d5dcd4a4b` | Passed — backend, worker, network-engine, frontend, and backup images |

The merged change starts Celery Beat in the production deployment command, publishes frontend and backup images on version-tag releases, includes the backup image in CI/Docker verification, and uses the dedicated `kravigil-backup` service account to avoid the base-image account collision. Regression tests cover the scheduler command, release image references, Docker backup build, and backup service account.

**Operational boundary:** no live staging deployment or scheduler tick evidence is claimed. KV-003 is closed for code/CI only; KV-008 remains blocked pending staging deployment and runtime acceptance. The release remains **NO-GO** until all applicable operational and governance gates in Section 5 are evidenced.


## 4.9 Exact-main reconciliation — 2026-11-05

**Current main SHA:** `fc298258a5b990500938bcab98602ac7704a97c0`  
**Latest merge:** PR [#72 — Reconcile release register after PR #71](https://github.com/mohamedelghazali/KRAVIGIL/pull/72).  
**Repository state at reconciliation:** no open pull requests; no published GitHub releases. The historical failed Docker workflow on an older PR commit is retained as history and is not the current-main result.

All three required workflows completed successfully on the exact current `main` SHA:

| Workflow | Run ID | Exact SHA | Result |
|---|---:|---|---|
| KRAVIGIL CI | [42086368327](https://github.com/mohamedelghazali/KRAVIGIL/actions/runs/42086368327) | `fc298258a5b990500938bcab98602ac7704a97c0` | Passed |
| Security Scans | [42086368382](https://github.com/mohamedelghazali/KRAVIGIL/actions/runs/42086368382) | `fc298258a5b990500938bcab98602ac7704a97c0` | Passed |
| Docker Image Build Verification | [42086368270](https://github.com/mohamedelghazali/KRAVIGIL/actions/runs/42086368270) | `fc298258a5b990500938bcab98602ac7704a97c0` | Passed — backend, worker, frontend, backup, and network-engine images |

The previous Docker backup-image account collision is fixed in the merged image definition; the five-image verification above confirms the current-main backup image builds. Do not reopen that repair absent a regression.

### Work-item state remains evidence-bounded

- KV-003 remains closed for code/CI; actual scheduler ticks are still part of KV-008 runtime acceptance.
- KV-007 remains blocked pending an isolated restore from the off-host replica, evidence-object integrity checks, and application smoke tests.
- KV-008 remains blocked pending a real staging deployment and runtime acceptance.
- KV-009 remains open pending representative staging load, resource/queue/storage telemetry, and approved SLOs.
- KV-010 remains blocked pending accountable production storage, retention, residency, RPO/RTO, and recovery decisions.
- KV-011 remains deferred to the final security-review phase.
- KV-012 remains open. The branch-protection API read returned HTTP 403 (integration permission unavailable); the previously observed unprotected state must be verified and configured by an authorized repository maintainer in GitHub settings.

**Release decision remains NO-GO.** Green exact-main workflows establish code/CI and image-build status only; they do not establish a deployed staging environment, a recoverable off-host backup, production capacity, or operational ownership.


## 4.10 PR #74 disaster-recovery procedure — merged; operational validation pending

**PR:** [#74 — Define operational disaster recovery procedure](https://github.com/mohamedelghazali/KRAVIGIL/pull/74)  
**Tested PR head:** `25bf09c81f8626d8b415ef967f0edddd2564ee90`  
**Merge commit / main SHA at this reconciliation:** `f67871ea80fd9c3b03d556f46a7b2b39f3f155fa`

The merged `docs/security/DISASTER_RECOVERY.md` now defines the recovery sequence: off-host backup selection, isolated PostgreSQL restore, restricted-role/RLS validation, separate evidence-object hash verification, isolated application smoke tests, cleanup, and an auditable drill record. It explicitly does not claim that a live restore or staging acceptance has occurred.

| Workflow | Run ID | Exact PR head | Result |
|---|---:|---|---|
| KRAVIGIL CI | `42104684052` | `25bf09c81f8626d8b415ef967f0edddd2564ee90` | Passed |
| Security Scans | `42104684446` | `25bf09c81f8626d8b415ef967f0edddd2564ee90` | Passed |
| Docker Image Build Verification | `42104684069` | `25bf09c81f8626d8b415ef967f0edddd2564ee90` | Passed |

Post-merge verification on exact `main` SHA `f67871ea80fd9c3b03d556f46a7b2b39f3f155fa` was started; at this reconciliation, Security Scans `42109558356` passed, while KRAVIGIL CI `42109558305` and Docker Image Build Verification `42109558529` were still running. Recheck these runs before treating post-merge validation as complete.

**Operational boundary:** KV-007 remains `BLOCKED` until an authorized off-host restore drill verifies the database, RLS, evidence-object hashes, isolated application workflows, cleanup, and measured RPO/RTO against approved objectives. KV-008 through KV-012 remain open/blocked/deferred as described above. Production remains **NO-GO**.


## 4.11 PR #75 work-register reconciliation — merged

**PR:** [#75 — Reconcile work register after PR #74](https://github.com/mohamedelghazali/KRAVIGIL/pull/75)  
**Tested PR head:** `fa076f4d0410437e81bd86e2dff17460b2938628`  
**Merge commit / current main SHA:** `5b162cf87203126b3f56f33ea71cf325602ee2ad`

All three required workflows passed on the exact PR head: KRAVIGIL CI `42109875150`, Security Scans `42109875265`, and Docker Image Build Verification `42109875153`. All three post-merge workflows also passed on the exact current `main` SHA: KRAVIGIL CI `42110018828`, Security Scans `42110018984`, and Docker Image Build Verification `42110018858`.

This entry supersedes the earlier PR #74 reconciliation as the current-main baseline. It does not change any operational acceptance state: KV-007 remains blocked pending a real off-host restore drill; KV-008 remains blocked pending staging runtime evidence; KV-009 remains open pending representative staging load, telemetry, and approved SLOs; KV-010 remains blocked pending production storage/recovery decisions; KV-011 remains deferred; KV-012 remains open pending verified branch protection. Production remains **NO-GO**.


## 4.12 PR #77 staging acceptance runbook — merged; runtime evidence pending

**PR:** [#77 — Define staging deployment and runtime acceptance](https://github.com/mohamedelghazali/KRAVIGIL/pull/77)  
**Tested PR head:** `6e8db62c5add6df79d0afb4fa3bc7c3da0c9548e`  
**Merge commit / main SHA at this reconciliation:** `3828bf1507ee3652bafd29f474f3a81cf783eff4`

All three required workflows passed on the exact PR head: KRAVIGIL CI [42382646151](https://github.com/mohamedelghazali/KRAVIGIL/actions/runs/42382646151), Security Scans [42382646144](https://github.com/mohamedelghazali/KRAVIGIL/actions/runs/42382646144), and Docker Image Build Verification [42382646112](https://github.com/mohamedelghazali/KRAVIGIL/actions/runs/42382646112). All three post-merge workflows also passed on exact `main` SHA `3828bf1507ee3652bafd29f474f3a81cf783eff4`: KRAVIGIL CI [42383764723](https://github.com/mohamedelghazali/KRAVIGIL/actions/runs/42383764723), Security Scans [42383764748](https://github.com/mohamedelghazali/KRAVIGIL/actions/runs/42383764748), and Docker Image Build Verification [42383764801](https://github.com/mohamedelghazali/KRAVIGIL/actions/runs/42383764801).

The merged `docs/operations/STAGING_ACCEPTANCE.md` defines environment isolation, pinned artifacts, health checks, authentication/MFA, tenant/RLS, scanner scope, scan/report/evidence workflows, scheduler/worker runtime proof, backup/replication, observability, and evidence-based PASS/INCOMPLETE/FAIL decisions.

**Operational boundary:** the runbook is documentation, not deployment evidence. KV-008 remains `BLOCKED — operational` until a real authorized staging deployment and the required runtime checks are recorded. KV-007, KV-009, KV-010, KV-011, and KV-012 remain at their existing evidence-bounded states. Production remains **NO-GO**.


## 4.9 PR #77 — Staging acceptance runbook — merged

**PR:** [#77 — Add staging acceptance runbook](https://github.com/mohamedelghazali/KRAVIGIL/pull/77)  
**Merge commit:** `3828bf1507ee3652bafd29f474f3a81cf783eff4`

The staging acceptance procedure is present in `docs/operations/STAGING_ACCEPTANCE.md`. It defines isolation, synthetic data, credentials, authorized scan scope, service health, authentication, tenant isolation, scan/report/evidence lifecycle, scheduler/worker evidence, backup/replication, observability, and PASS / INCOMPLETE / FAIL outcomes. This is a runbook only; it does not prove a live staging deployment. KV-008 remains operationally blocked.

## 4.10 PR #78 — Off-host restore evidence template — merged

**PR:** [#78 — Prepare off-host restore drill evidence pack](https://github.com/mohamedelghazali/KRAVIGIL/pull/78)  
**Tested head SHA:** `8719914c20ff693314250743a088dfbabff3e59b`  
**Merge commit:** `98ade9baa970c9d09f7f5f5843fe6f6ac9a06ddd`

Added `docs/operations/RESTORE_DRILL_EVIDENCE_TEMPLATE.md` and reconciled the work register with PR #77. The template captures authorization, off-host artifact identity, checksums, decryption, PostgreSQL restore, restricted-role/RLS checks, evidence object integrity, application smoke tests, scheduler/worker checks, measured RPO/RTO, cleanup, and independent sign-off. It does not prove a real restore; KV-007 remains operationally blocked.

The following post-merge workflows passed on the exact PR #78 merge commit:

| Workflow | Run ID | Exact SHA | Result |
|---|---:|---|---|
| KRAVIGIL CI | `42383764723` | `3828bf1507ee3652bafd29f474f3a81cf783eff4` | Passed |
| Security Scans | `42383764748` | `3828bf1507ee3652bafd29f474f3a81cf783eff4` | Passed |
| Docker Image Build Verification | `42383764801` | `3828bf1507ee3652bafd29f474f3a81cf783eff4` | Passed |

The required PR-head workflows also passed before PR #78 was merged.

## 4.11 PR #79 — Deployment and release procedures — merged

**PR:** [#79 — Make deployment and release procedures executable](https://github.com/mohamedelghazali/KRAVIGIL/pull/79)  
**Tested PR head SHA:** `95e14187daf039985d050e5b0590b290f5ebd39b`  
**Merge commit / current main SHA:** `fed45598a88c409a34e50c16b660815becd3d4a2`

The PR corrected the production deployment command to `bash scripts/deploy_prod.sh`, replaced the deployment operations scaffold with an operational index, and documented the tag-triggered release workflow and five GHCR image artifacts. It is documentation-only and does not constitute a deployment or release publication.

All three required workflows passed on the exact PR head:

| Workflow | Run ID | Exact tested head | Result |
|---|---:|---|---|
| KRAVIGIL CI | `42385541953` | `95e14187daf039985d050e5b0590b290f5ebd39b` | Passed |
| Security Scans | `42385541978` | `95e14187daf039985d050e5b0590b290f5ebd39b` | Passed |
| Docker Image Build Verification | `42385541917` | `95e14187daf039985d050e5b0590b290f5ebd39b` | Passed |

Post-merge workflows were triggered on `fed45598a88c409a34e50c16b660815becd3d4a2`; at reconciliation time all three were still running. Do not mark post-merge verification complete until their final results are recorded.

## 4.12 Current GitHub state — 2026-11-07

**Current main SHA:** `fed45598a88c409a34e50c16b660815becd3d4a2`

| Workflow | Run ID | Exact main SHA | State at reconciliation |
|---|---:|---|---|
| KRAVIGIL CI | `42386395700` | `fed45598a88c409a34e50c16b660815becd3d4a2` | In progress |
| Security Scans | `42386395720` | `fed45598a88c409a34e50c16b660815becd3d4a2` | In progress |
| Docker Image Build Verification | `42386395677` | `fed45598a88c409a34e50c16b660815becd3d4a2` | In progress |

Previously completed CI, Security, and Docker results on `3828bf1507ee3652bafd29f474f3a81cf783eff4` remain valid only for that earlier commit; they do not substitute for the post-PR #79 checks.

## 4.13 Next execution order — GitHub-first, Staging last

The agreed execution order is:

1. Finish and record all GitHub workflows on the current main SHA after PR #79.
2. Reconcile this register and close any remaining repository-only release-readiness gaps.
3. Configure and verify main branch protection and required status checks (KV-012).
4. Complete repository-verifiable build, release, deployment configuration, and documentation checks without provisioning Staging.
5. Only after the GitHub/repository readiness phase is complete, provision isolated Staging and execute KV-007, KV-008, and KV-009 with real evidence.
6. Complete the deferred final security review (KV-011) after functional and operational acceptance, as previously agreed.

KV-007, KV-008, and KV-009 remain blocked on real infrastructure/evidence. KV-010 requires explicit provider, residency, retention, ownership, and RPO/RTO decisions. Production remains **NO-GO**.


## 4.14 PR #80 — work-register reconciliation and exact-main verification — merged

**PR:** [#80 — Reconcile release readiness after PRs 77–79](https://github.com/mohamedelghazali/KRAVIGIL/pull/80)  
**Tested PR head SHA:** `8ce4c824fe5c51ab1640cae9a3f6324169a8b361`  
**Merge commit / current main SHA:** `8728c04f563c1f47a7dccb9462673bbdeea9538b`

PR #80 reconciled the work register after PRs #77–#79. After merge, all three required workflows completed successfully on the exact current `main` SHA:

| Workflow | Run ID | Exact main SHA | Result |
|---|---:|---|---|
| KRAVIGIL CI | [42388174081](https://github.com/mohamedelghazali/KRAVIGIL/actions/runs/42388174081) | `8728c04f563c1f47a7dccb9462673bbdeea9538b` | Passed |
| Security Scans | [42388174158](https://github.com/mohamedelghazali/KRAVIGIL/actions/runs/42388174158) | `8728c04f563c1f47a7dccb9462673bbdeea9538b` | Passed |
| Docker Image Build Verification | [42388174104](https://github.com/mohamedelghazali/KRAVIGIL/actions/runs/42388174104) | `8728c04f563c1f47a7dccb9462673bbdeea9538b` | Passed — backend, worker, network-engine, frontend, and backup images |

Repository state was rechecked after the workflows: no open pull requests. The `main` branch remains unprotected (`protected: false`); required status-check enforcement is off and no required contexts are configured. KV-012 therefore remains open and requires an authorized maintainer to configure repository rules.

**Operational boundary:** the successful workflows establish exact-main CI, security-scan, and container-image build status only. They do not prove a live Staging deployment, off-host restore, measured capacity, or production acceptance. KV-007, KV-008, and KV-009 remain operationally blocked; KV-010 remains a decision blocker; KV-011 remains deferred to the final phase. Production remains **NO-GO**.

## 4.15 Next execution order — repository closeout before Staging

1. Complete KV-012 by configuring and verifying a `main` branch ruleset with pull-request protection and required checks.
2. Finish any remaining repository-verifiable release/configuration checks without provisioning Staging.
3. After repository closeout, provision isolated Staging and execute KV-007, KV-008, and KV-009 with real evidence.
4. Complete the deferred final security review (KV-011) after functional and operational acceptance.

KV-010 requires explicit storage-provider, residency, retention, recovery ownership, and RPO/RTO decisions. Production remains **NO-GO** until all applicable gates have evidence.


## 4.16 PR #81 — exact-main reconciliation — merged

**PR:** [#81 — Reconcile exact-main verification after PR #80](https://github.com/mohamedelghazali/KRAVIGIL/pull/81)  
**Tested PR head SHA:** `d4f348648255a9b7046a81c4c6875c9d0b0f7ce1`  
**Merge commit / current main SHA:** `31301b893e6744ec77d464ece02646f5abf0735d`

All three required workflows passed on the exact PR head, and all three post-merge workflows passed on the exact current `main` SHA:

| Workflow | Run ID | Exact main SHA | Result |
|---|---:|---|---|
| KRAVIGIL CI | [42390525884](https://github.com/mohamedelghazali/KRAVIGIL/actions/runs/42390525884) | `31301b893e6744ec77d464ece02646f5abf0735d` | Passed |
| Security Scans | [42390525885](https://github.com/mohamedelghazali/KRAVIGIL/actions/runs/42390525885) | `31301b893e6744ec77d464ece02646f5abf0735d` | Passed |
| Docker Image Build Verification | [42390526021](https://github.com/mohamedelghazali/KRAVIGIL/actions/runs/42390526021) | `31301b893e6744ec77d464ece02646f5abf0735d` | Passed — backend, worker, network-engine, frontend, and backup images |

The commit exposes 12 completed check-runs, all successful, including backend tests, C++ build, frontend build, lint/format, Python security, secret scan, and all five image builds. No open pull requests were present at reconciliation. No published GitHub releases were found.

**KV-012 remains OPEN:** the repository rulesets API returned an empty list. The branch-protection read endpoint returned HTTP 403 to this integration, so classic branch-protection state could not be independently read. An authorized maintainer must configure the `main` ruleset and verify required status checks in GitHub settings.

**Operational boundary:** these results establish repository CI and image-build status only. KV-007, KV-008, and KV-009 still require real infrastructure evidence; KV-010 requires explicit storage/recovery decisions; KV-011 remains deferred to the final phase. Production remains **NO-GO**.

## 4.17 Next execution order

1. Configure and verify `main` branch protection / required status checks (KV-012).
2. Finish any remaining repository-verifiable release/configuration checks without provisioning Staging.
3. Only then provision isolated Staging and execute KV-007, KV-008, and KV-009 with evidence.
4. Complete the deferred final security review (KV-011) after operational acceptance.

# KRAVIGIL Release Closure Execution Plan

**Status:** ACTIVE — release remains NO-GO  
**Base:** `main`  
**Execution branch:** `release/closure-execution`  
**Rule:** This plan records evidence-backed closure. A checkbox is not complete until the linked code, tests, and CI evidence exist on the same commit.

## Release invariants

1. Do not push directly to `main`; all changes are proposed through pull requests.
2. Do not merge while required checks fail, are pending, or are missing.
3. Do not remove scaffold markers without implementing the behavior or formally removing the capability from runtime exports, routes, configuration, and documentation.
4. Do not claim production readiness from unit tests, a successful build, or a deployment script alone.
5. Never use test-only S3Mock as production evidence storage.
6. Do not silently choose a production object-storage vendor, retention policy, data residency, or recovery objective. These are operational decisions that must be documented and verified before production acceptance.

## Workstreams and acceptance gates

| ID | Workstream | Required closure evidence | Current status |
|---|---|---|---|
| W0 | Baseline and inventory | Exact base SHA, complete scaffold inventory, current workflows and required checks recorded | In progress |
| W1 | Scaffold disposition (87 files) | Every file implemented with focused tests, or safely de-scoped with zero runtime references; issue #1 checklist reconciled | In progress — severity/status enums and focused tests added; CI and integration pending |
| W2 | Core integration | API, DB models/repositories, schemas, services, workers, scanner adapters, and UI contracts exercised end-to-end | Not started |
| W3 | CI and code quality | Backend tests, migrations/RLS, Ruff, MyPy, Black, frontend locked install/build, C++ tests, secret/dependency/security scans all pass on one SHA | In progress — Gitleaks shallow-checkout failure diagnosed and fixed on execution branch; rerun pending |
| W4 | Container supply chain | Backend, worker, and network-engine images independently build and publish/verify on the same SHA; pinned base/runtime images | Not verified |
| W5 | Production storage | Supported S3-compatible provider selected; Compose, replication, backup, retention, TLS, IAM and restore tested against it | Blocked by provider/operations decision |
| W6 | Production security and operations | Tenant isolation across API/workers, secrets/rotation, HTTPS/cert renewal, queue recovery, monitoring/alerts, runbooks, resource/load tests | Not executed |
| W7 | Recovery and release acceptance | Encrypted backup plus isolated restore drill, evidence integrity/replication checks, final review with exact SHA and workflow URLs | Not executed |

## W1 — 87-file scaffold disposition

The authoritative per-file inventory and acceptance contract remain in [issue #1](https://github.com/mohamedelghazali/KRAVIGIL/issues/1). Treat all 87 entries as open until individually evidenced. Work should be split into reviewable batches:

- Shared contracts, enums, and schemas
- Database models and repositories
- API dependencies and endpoints
- Security controls (RBAC, mTLS, tenant isolation)
- Scanner adapters and web detectors
- Normalization, correlation, differential analysis, and feedback services
- AI gateway/providers/models and prompt/evidence controls
- Workers, scheduling, scope enforcement, and reporting
- Integration, regression, performance, and security tests

Each batch must include caller compatibility, negative/boundary tests, and a reference to its CI run. Security-sensitive and scanner code must fail closed, enforce explicit scope, use safe process argument arrays, bounded timeouts/output, and emit auditable outcomes.

## Immediate engineering sequence

1. Reconcile the inventory against the current branch and identify actual callers before editing any scaffold.
2. Implement or de-scope one coherent vertical slice at a time; add tests in the same change.
3. Resolve frontend dependency reproducibility by committing the correct lockfile and using `npm ci`.
4. Make Black formatting deterministic and clean the existing formatting debt without mixing unrelated functional changes.
5. Remove Pydantic deprecation warnings only with compatibility tests for serialized API contracts.
6. Resolve production storage only after recording provider, retention/Object Lock, replication, backup, restore, residency, and cost requirements.
7. Run full CI and production acceptance; update `docs/FINAL_REVIEW.md` with evidence and exact SHA.

## Current release decision

**NO-GO.** The repository review currently identifies 87 explicit Python scaffolds, unresolved production object storage, incomplete image-workflow evidence, and unexecuted production/restore acceptance. This plan does not change that decision. The release gate changes to GO only when every applicable workstream above has verifiable evidence on the same candidate commit and independent review has approved it.

## Execution log

- 2026-11-04: Created `release/closure-execution` from the reviewed `main` baseline and opened draft PR #2.
- 2026-11-04: Implemented the canonical severity and lifecycle enums in `shared/enums/severity.py` and `shared/enums/status.py`; added focused unit tests in `tests/unit/test_shared_enums.py`. These remain pending CI and caller-integration acceptance and are not yet counted as closed issue #1 entries.
- 2026-11-04: Diagnosed the initial Gitleaks job failure as an incomplete shallow checkout (the action could not resolve the PR base commit range; no secret finding was reported in that failed run). Updated `.github/workflows/security-scan.yml` to fetch full history. The corrected workflow result is pending.

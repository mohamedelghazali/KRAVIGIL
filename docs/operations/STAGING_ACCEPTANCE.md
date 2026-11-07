# KRAVIGIL — Staging Deployment and Runtime Acceptance

**Status:** Procedure prepared; no live staging deployment or runtime pass is claimed.  
**Work item:** KV-008.  
**Dependencies:** KV-007 recovery drill; KV-010 provider, residency, retention, and recovery decisions.  
**Release status:** Production remains **NO-GO** until all release gates have evidence.

## 1. Safety boundary

- Use a dedicated staging host/account, isolated database, Redis, object-storage buckets, and synthetic test tenants.
- Do not point staging at production databases, queues, buckets, credentials, SMTP accounts, scanner engines, or monitoring write targets.
- Restrict scanner egress to explicitly authorized assets owned or controlled by the operator. Use a private lab target by default; never use public or third-party targets for this test.
- Keep credentials in an approved secret manager or protected environment injection. Never commit `.env`, tokens, private keys, recovery passphrases, or raw customer evidence.
- Record timestamps in UTC and capture the exact application Git SHA and immutable image digests.

## 2. Entry criteria

Do not begin runtime acceptance until the accountable service owner confirms:

- [ ] Named staging owner, operator, and approver.
- [ ] Dedicated staging hostname, TLS certificates, network boundaries, firewall rules, and restricted operator access.
- [ ] Staging-only `.env` populated from `.env.example`, with unique non-placeholder secrets.
- [ ] Independent staging credentials and buckets for primary and off-host object storage; replication target is HTTPS and in a separate failure domain.
- [ ] Disposable PostgreSQL database and isolated Redis service.
- [ ] Synthetic tenant, administrator, and test data; no production credentials or customer records.
- [ ] Scanner scope allowlist contains only controlled lab targets.
- [ ] Rollback/cleanup owner and approved cleanup window.
- [ ] Staging-specific KV-010 exceptions or decisions recorded without representing them as production decisions.

If any entry criterion is missing, keep KV-008 BLOCKED and stop before deployment.

## 3. Candidate identity

1. Select a reviewed commit from `main`; record its full SHA.
2. Build or pull images by immutable digest; do not use mutable `latest` tags as acceptance identity.
3. Record Compose revision, host OS/kernel, Docker Engine/Compose versions, CPU/RAM/disk limits, network topology, PostgreSQL/Redis/object-store versions, and image digests.
4. Verify KRAVIGIL CI, Security Scans, and Docker Image Build Verification passed on the exact candidate SHA.
5. Confirm staging endpoints and credentials are distinct from production. Never include secret values in evidence.

## 4. Deployment and service health

Use the approved staging deployment procedure for the selected topology. Do not run the production deployment script against an unreviewed or shared host.

Record the following:

- [ ] Database and Redis health checks pass.
- [ ] MinIO/S3 endpoint and bucket access work with least-privilege staging credentials.
- [ ] Network engine health passes and backend/worker mTLS identities validate.
- [ ] Backend, frontend, nginx, worker, scheduler, Prometheus, Grafana, and backup services run with expected replica counts and no restart loop.
- [ ] `/api/v1/system/health` reports healthy dependencies; liveness alone is insufficient.
- [ ] TLS hostname, validity, chain, and renewal monitoring are verified.
- [ ] Logs contain no secrets, tokens, passphrases, or unexpected tenant data.
- [ ] Alerts reach the designated staging notification destination.

Suggested read-only inspection commands (adjust Compose files to the approved staging topology):

```bash
docker compose ps
docker compose logs --since=30m backend worker scheduler db redis
docker compose logs --since=30m minio network_engine backup
```

Do not expose the Docker socket or monitoring interfaces publicly to perform these checks.

## 5. Functional runtime acceptance

Run tests only with designated staging accounts and synthetic tenant data. Preserve request IDs and redacted outputs, not credentials or raw sensitive payloads.

- [ ] Administrator login and MFA enrollment/challenge/recovery work as configured.
- [ ] Tenant A accesses only its own targets, scans, findings, reports, and evidence.
- [ ] Tenant B cannot read, update, delete, or infer Tenant A records through API or direct database access using restricted `kravigil_app`.
- [ ] Authorized lab target creation and scope validation work.
- [ ] A scan against a controlled lab target is dispatched, processed by a worker, and reaches a terminal state with persisted result/error metadata.
- [ ] Findings and reports are generated and retrievable by the owning tenant.
- [ ] Evidence upload, retrieval, integrity verification, and deletion/tombstone reconciliation work.
- [ ] Password-reset email reaches a controlled test mailbox if SMTP reset is enabled.
- [ ] Rate limiting, authorization failures, and invalid-scope requests behave as expected.
- [ ] No staging workflow can dispatch scans to an unapproved external target.

Mocked unit/E2E tests do not substitute for these live staging observations.

## 6. Scheduler and worker runtime proof

KV-003 is closed for code/CI only. KV-008 must demonstrate actual runtime execution.

- [ ] Exactly one active Celery Beat scheduler instance runs for the staging deployment.
- [ ] Scheduler logs show the expected periodic task and at least one actual due/dispatch event.
- [ ] Broker/queue evidence shows the scheduled task was enqueued.
- [ ] Worker logs and task result show start and completion (or a documented expected no-op) with a correlation/task ID.
- [ ] Retry and failure persistence behavior is verified with a controlled, non-destructive test.
- [ ] No duplicate scheduler instances or duplicate periodic execution occurred during the observation window.

A running container, startup log, or configured schedule alone does not prove scheduler acceptance.

## 7. Backup and recovery integration

KV-007 remains a separate gate and must pass its dedicated off-host restore drill. For staging acceptance:

- [ ] A staging backup completes and backup-service health reflects success.
- [ ] Encrypted backup and checksum sidecar exist in the staging source bucket.
- [ ] The same object is visible in the off-host staging replica and replication status is healthy.
- [ ] Evidence objects are replicated and representative hashes match.
- [ ] Source and target retention/lifecycle rules match the approved staging policy.
- [ ] Recovery uses a disposable isolated database and the off-host replica, following [Backup and Restore Runbook](BACKUP_AND_RESTORE.md).

A successful backup job does not close KV-007. Only the complete, approved restore evidence package can do that.

## 8. Observability

Capture a timestamped baseline and observation window covering:

- API health and HTTP status/error rates.
- Backend and worker CPU/memory/restarts.
- Celery queue depth, oldest-message age, task duration, retries, and failures.
- PostgreSQL connections, pool waits, query latency, disk use, and replication/failover state where applicable.
- Redis memory, latency, connectivity, and queue behavior.
- Object-store availability, request latency, capacity, replication status, and errors.
- Network-engine health, utilization, and task outcomes.
- Prometheus scrape health, Grafana dashboards, alert firing, and alert delivery.

Dashboards or successful scraping do not prove thresholds are appropriate or alerts actionable.

## 9. Evidence and acceptance decision

Create one access-controlled evidence package per staging candidate:

| Evidence | Required contents |
|---|---|
| Identity | Candidate SHA, image digests, Compose/config revision |
| Environment | Host/runtime versions, topology, resource limits, network diagram |
| Deployment | Redacted configuration, deployment timestamps, service health |
| Security | TLS/mTLS validation, restricted-role RLS results, tenant isolation |
| Functional | Test IDs, synthetic tenant IDs, request/task correlation IDs, outcomes |
| Scheduler | Beat due/dispatch log, queue evidence, worker completion evidence |
| Backup | Backup key/version, checksum, replication and retention evidence |
| Observability | Timestamped metrics, dashboards, alert delivery and logs |
| Defects | Linked issues, severity, owner, remediation and retest SHA |
| Approval | Named operator, reviewer, decision, date, explicit exceptions |

KV-008 is PASS only when all mandatory tests pass on the same candidate SHA, evidence is retained, defects are closed or formally risk-accepted, and the accountable approver signs. Missing evidence is INCOMPLETE; a failed security, tenant-isolation, data-integrity, or scope-control test is FAIL.

## 10. Current status

No live staging host, deployment, runtime logs, scheduled task execution, alert delivery, or signed acceptance evidence has been verified. Therefore KV-008 remains **BLOCKED — operational evidence pending**. This document prepares execution; it does not close the gate.

Production remains **NO-GO** until KV-007 through KV-012 are independently satisfied with their required evidence.

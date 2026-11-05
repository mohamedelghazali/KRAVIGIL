# KRAVIGIL — Disaster Recovery Plan

**Status:** Operational procedure defined; disaster-recovery acceptance is **NOT YET VERIFIED**.  
**Related work items:** KV-007 (backup and restore), KV-008 (staging/runtime acceptance), KV-010 (production recovery decisions).  
**Canonical procedure:** [Backup and Restore Runbook](../operations/BACKUP_AND_RESTORE.md).

This document defines the recovery sequence and the evidence required to demonstrate recoverability. It does not claim that a restore drill, production deployment, or an approved RPO/RTO has occurred.

## 1. Recovery principles and boundaries

1. Treat the primary application host, PostgreSQL volume, local MinIO service, and their credentials as one potential failure domain.
2. For a disaster-recovery exercise, retrieve the PostgreSQL backup from the configured **off-host HTTPS S3-compatible replica**, not from the primary MinIO service.
3. Recover PostgreSQL and object-store evidence as separate data planes. A PostgreSQL custom-format dump does **not** contain MinIO evidence objects.
4. Never restore into the production database. Use a newly created, isolated recovery database and restricted network access.
5. Keep the backup encryption passphrase in an independent secrets manager or offline escrow. Do not place it beside the backup, in this repository, in logs, or in the evidence report.
6. Do not infer recoverability from a green CI run, a healthy backup container, replication configuration, or object listing alone.
7. Record actual measured recovery times and observed data-loss window. Do not invent or silently adopt RPO/RTO targets.

## 2. Recovery dependencies and ownership

Before an exercise or real recovery, an authorized recovery operator must have:

- Access to the off-host object-store endpoint and a read-capable credential for the backup and evidence buckets.
- Independently escrowed `BACKUP_ENCRYPTION_KEY`.
- A disposable PostgreSQL recovery instance and administrator capable of creating an empty database and provisioning the restricted application role.
- A trusted recovery host with Python 3.11, the pinned MinIO Python client, GnuPG, and PostgreSQL client tools compatible with the backup.
- The approved application release/configuration and a secure way to inject temporary recovery credentials.
- An isolated network and named operator/approver.

**Decision still required under KV-010:** production storage provider, data residency, retention and immutability policy, named recovery owner, approved RPO/RTO, and cost/availability trade-offs. These must be approved by the service owner; this plan does not assign values.

## 3. Recovery sequence

### Phase A — Declare and isolate

1. Record incident/exercise identifier, UTC start time, operator, approver, and recovery scope.
2. Confirm that the target PostgreSQL instance, object-store endpoint, and application environment are isolated from production.
3. Confirm that no production database name, host, credentials, or writable production endpoint is configured in the restore environment.
4. Capture the approved recovery target and the intended database name before handling backup material.

### Phase B — Select an off-host backup

1. Authenticate to the off-host recovery bucket using the approved read-only or least-privilege credential.
2. List candidate objects under `postgresql/`; select a specific `.dump.gpg` object and its adjacent `.sha256` sidecar.
3. Record the exact object key, object timestamp/version where available, encrypted object size, and sidecar presence.
4. Confirm that the selected object is available from the off-host endpoint, not merely the primary MinIO service.
5. Keep the selected object immutable during the drill. Do not delete, overwrite, or alter source or replica objects.

### Phase C — Restore PostgreSQL in isolation

Follow the exact command and environment contract in [Backup and Restore Runbook](../operations/BACKUP_AND_RESTORE.md).

1. Create a new, empty recovery database on the isolated PostgreSQL instance.
2. Configure `MINIO_ENDPOINT` and credentials to point to the off-host replica. Set `BACKUP_OBJECT_KEY` to the exact selected key.
3. Configure `RESTORE_DB_HOST`, `RESTORE_DB_PORT`, `RESTORE_DB_NAME`, `RESTORE_DB_USER`, and `RESTORE_DB_PASSWORD` for the isolated target only.
4. Set `DB_NAME` to the production database name as the restore utility's safety guard, and set `RESTORE_CONFIRMATION` to exactly the recovery database name.
5. Inject the independently escrowed passphrase securely. Never put secrets on the command line or in the evidence report.
6. Run `python infrastructure/backup/pg_restore.py` from a trusted checkout of the intended release.
7. Capture exit status, UTC start/end times, checksum verification result, archive validation result, and restore duration. Redact all secrets.

The restore utility verifies the encrypted artifact against its SHA-256 sidecar, decrypts it in a temporary directory, validates the PostgreSQL archive, and invokes `pg_restore` with `--exit-on-error` and `--single-transaction`. A successful command is necessary but not sufficient for recovery acceptance.

### Phase D — Recreate database roles and verify RLS

The backup is created with `--no-owner --no-acl`; PostgreSQL roles and grants are not included in the dump.

1. Recreate the restricted `kravigil_app` role using the role-provisioning SQL maintained in `scripts/deploy_prod.sh`, adapted only for the isolated recovery database.
2. Verify that the application role is `NOSUPERUSER` and `NOBYPASSRLS`, and has only the intended database/schema/table/sequence privileges.
3. Verify the expected RLS policies exist and are enabled/forced on tenant-owned tables.
4. Execute the PostgreSQL RLS integration checks with the restricted application role, including cross-tenant read/write denial. Do not treat tests run only with a superuser as RLS evidence.

### Phase E — Verify object-store evidence

1. Confirm that the corresponding evidence bucket is available from the off-host object-store recovery endpoint.
2. Compare the recovered evidence objects against the object keys and SHA-256 metadata referenced by the restored database.
3. Download representative objects and recompute their hashes; compare exact values with the stored metadata.
4. Include coverage for multiple tenants and object sizes/types where present. Record missing objects, mismatches, inaccessible versions, or metadata inconsistencies as failures.
5. Do not assume a PostgreSQL restore recovers evidence files. Do not mark the drill successful if required evidence objects are absent or cannot be verified.

### Phase F — Isolated application smoke tests

Only after Phases C–E pass:

1. Start the application in the isolated recovery/staging environment with recovery-only credentials and network access.
2. Verify health endpoints and database connectivity.
3. Verify login and MFA behavior using designated test accounts.
4. Verify representative tenant-scoped target, scan, finding, report, and evidence retrieval workflows.
5. Verify background worker and scheduler behavior without connecting to production services or launching scans against real external targets.
6. Capture application logs and test outcomes, ensuring credentials, tokens, passphrases, and sensitive customer data are redacted.

### Phase G — Close and clean up

1. Stop isolated application services and revoke temporary credentials.
2. Preserve only approved, redacted evidence artifacts and logs.
3. Securely destroy disposable recovery databases, volumes, downloaded backup files, decrypted dumps, and temporary secrets according to the approved handling policy.
4. Record cleanup confirmation and any residual artifacts.
5. File defects as linked work items; do not overwrite a failed drill report with a later successful result.

## 4. Acceptance criteria

A restore drill is **PASS** only when every applicable item below has evidence:

- [ ] Backup object and matching checksum sidecar were retrieved from the off-host replica.
- [ ] Encrypted backup SHA-256 matched the sidecar.
- [ ] GPG decryption and PostgreSQL archive validation succeeded.
- [ ] Restore completed in a newly created isolated database, with the production-target safety guard active.
- [ ] Expected schema and migration version are present.
- [ ] Restricted application role and grants were recreated and verified.
- [ ] PostgreSQL RLS checks passed with the restricted role, including cross-tenant denial.
- [ ] Evidence objects required by the restored database were available from the off-host replica and their hashes matched.
- [ ] Isolated application health, authentication/MFA, and representative workflows passed.
- [ ] Actual RPO observation and measured RTO were recorded and compared with formally approved objectives.
- [ ] Temporary credentials, decrypted artifacts, and recovery resources were cleaned up.
- [ ] An approver reviewed and accepted the evidence package.

Any missing evidence, checksum mismatch, absent evidence object, RLS failure, production connectivity, or unapproved RPO/RTO comparison makes the drill **FAIL** or **INCOMPLETE**; do not report a partial pass as recovery acceptance.

## 5. Recovery drill evidence record

Create one immutable, access-controlled record per exercise. Include:

| Field | Required value |
|---|---|
| Exercise / incident ID | Unique identifier |
| Date and operator | UTC timestamps and responsible operator |
| Approver | Named reviewer |
| Application release | Git commit SHA and image digests |
| Backup source | Off-host provider/endpoint identifier (no secrets) |
| Backup object | Exact object key, version if available, timestamp, size |
| Integrity | Sidecar SHA-256 and calculated SHA-256 result |
| Restore target | Isolated host/database identifier (no credentials) |
| Restore duration | Start/end UTC and elapsed time |
| Database validation | Schema, migration, expected records, RLS outcomes |
| Evidence validation | Objects checked, hashes matched, missing/mismatched count |
| Application validation | Health, login/MFA, scan/report/evidence smoke tests |
| Recovery objectives | Approved RPO/RTO reference and measured result |
| Cleanup | Temporary resources and credentials revoked/deleted |
| Result | PASS / FAIL / INCOMPLETE with linked logs and defects |

Never include passwords, access keys, bearer tokens, encryption passphrases, private keys, or raw customer evidence in this record.

## 6. Current acceptance status

As of this document revision:

- Backup and restore utilities, a runbook, and unit tests exist.
- Unit tests exercise safety guards, checksum mismatch handling, and restore command flags using mocked object storage and subprocess calls.
- No verified off-host restore drill, restored evidence-object integrity report, or isolated application recovery report is recorded.
- Production RPO/RTO and recovery ownership remain unapproved.

Therefore **KV-007 remains BLOCKED — operational evidence pending**, and production release remains **NO-GO**. KV-008 and KV-010 remain separate gates; this document does not close them.

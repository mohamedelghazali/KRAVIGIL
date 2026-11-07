# KRAVIGIL — Off-host Restore Drill Evidence Record

**Purpose:** Capture one controlled KV-007 recovery exercise without exposing credentials, customer data, or production connectivity. Complete this record for each exercise and preserve the original result. A later successful drill must be a new record, not an overwrite of a failed or incomplete one.

**Status:** Template only. No restore drill is implied by this file.

## 1. Exercise control

| Field | Recorded value |
|---|---|
| Exercise ID | |
| Exercise date | |
| Operator | |
| Independent approver | |
| Change / authorization reference | |
| Start time (UTC) | |
| End time (UTC) | |
| Result | NOT RUN / INCOMPLETE / FAIL / PASS |

## 2. Scope and isolation preflight

Mark each item only after verifying it. Any failed safety item is a hard stop.

- [ ] Written authorization and named operator/approver are recorded.
- [ ] Recovery host, PostgreSQL target, object-store endpoint, and application environment are isolated from production.
- [ ] No production database endpoint, production credentials, or writable production object-store endpoint is configured.
- [ ] Recovery database is newly created and has a distinct name from the production database.
- [ ] Off-host replica endpoint is independently identified; it is not the primary MinIO host or failure domain.
- [ ] Synthetic/test identities and data will be used for application smoke tests.
- [ ] Scanner tests are restricted to a controlled lab target owned by the operator or explicitly authorized in writing.
- [ ] Temporary credentials are least-privilege, short-lived, and delivered through an approved secrets manager.
- [ ] Encryption key/passphrase is independently escrowed and is not stored in this record, shell history, command arguments, repository, or logs.
- [ ] Recovery host tool versions are compatible with the selected backup and application release.

**Hard-stop rule:** If any isolation, authorization, target-separation, or secret-handling check is false or unknown, stop. Record INCOMPLETE; do not attempt a restore.

## 3. Recovery artifact identification

| Field | Recorded value |
|---|---|
| Off-host provider / endpoint identifier (non-secret) | |
| Backup bucket identifier | |
| Backup object key | |
| Object version ID (if supported) | |
| Object timestamp (UTC) | |
| Encrypted object size | |
| Checksum sidecar key | |
| Sidecar SHA-256 | |
| Independently calculated SHA-256 | |
| Checksum result | NOT RUN / MATCH / MISMATCH |
| Evidence bucket identifier | |
| Application source commit SHA | |
| Application image digests | |

Do not paste signed URLs, access keys, tokens, passwords, encryption material, or customer evidence into this record.

## 4. Restore execution

| Step | Start (UTC) | End (UTC) | Exit/result | Evidence reference |
|---|---|---|---|---|
| Off-host object retrieval | | | | |
| SHA-256 verification | | | | |
| GPG decryption | | | | |
| PostgreSQL archive listing/validation | | | | |
| Restore into isolated recovery DB | | | | |
| Schema and migration validation | | | | |
| Restricted role recreation | | | | |
| RLS verification with restricted role | | | | |
| Evidence-object integrity checks | | | | |
| Isolated application smoke tests | | | | |
| Cleanup and credential revocation | | | | |

Record actual command exit codes and redacted log references. Do not include raw secret-bearing command lines.

## 5. Database and tenant-isolation evidence

- [ ] Restore used the off-host object and matching checksum sidecar.
- [ ] Restore utility's production-target guard remained active.
- [ ] PostgreSQL archive validation passed.
- [ ] Restore completed transactionally into the isolated recovery database.
- [ ] Expected schema and migration revision were verified.
- [ ] Restricted application role was recreated because the backup excludes ownership/ACLs.
- [ ] Application role was verified as NOSUPERUSER and NOBYPASSRLS.
- [ ] Expected tenant RLS policies were present and ENABLE/FORCE state was verified.
- [ ] Cross-tenant read, insert, update, and delete denial were tested using the restricted application role.
- [ ] Worker tenant context was validated without leaking context across reused connections.

Evidence references and concise outcomes:

| Test / query reference | Expected result | Actual result | Evidence link |
|---|---|---|---|
| Role attributes | NOSUPERUSER, NOBYPASSRLS | | |
| RLS policy inventory | Expected policies present and forced | | |
| Cross-tenant read | Denied / no rows | | |
| Cross-tenant write | Denied | | |
| Cross-tenant update/delete | Denied | | |
| Worker tenant-context cleanup | Context cleared between tasks | | |

## 6. Evidence object recovery

A PostgreSQL dump does not contain MinIO/S3 evidence objects. Verify the object plane independently.

| Metric | Recorded value |
|---|---|
| Database-referenced evidence objects sampled / total in scope | |
| Objects retrieved from off-host replica | |
| SHA-256 matches | |
| Missing objects | |
| Hash mismatches | |
| Inaccessible versions / metadata failures | |

- [ ] Object keys referenced by restored database records were reconciled with the replica.
- [ ] Representative objects across tenants, sizes, and supported types were downloaded in isolation.
- [ ] Recomputed SHA-256 values matched trusted stored metadata.
- [ ] No missing or mismatched required object remains unresolved.

Any missing required object or hash mismatch prevents PASS.

## 7. Isolated application and background processing

- [ ] Health endpoint passed and database connectivity was confirmed.
- [ ] Login and MFA passed using designated synthetic test accounts.
- [ ] Tenant-scoped target and finding retrieval passed.
- [ ] Scan/report/evidence lifecycle smoke tests passed using a controlled lab target only.
- [ ] Worker consumed and completed an authorized test task.
- [ ] Scheduler emitted and dispatched a due test task.
- [ ] No duplicate task execution or cross-tenant data access was observed.
- [ ] Logs, metrics, and alerts were reviewed; secrets and sensitive data were redacted.

Record the exact tested app SHA and image digests. Do not infer runtime health from CI or image builds.

## 8. Recovery objectives and measurements

| Measure | Approved objective / reference | Actual observation |
|---|---|---|
| RPO | Must be formally approved under KV-010 | |
| Observed data-loss window | Measure from backup timestamp and recovery point | |
| RTO | Must be formally approved under KV-010 | |
| Elapsed recovery time | Record measured start/end UTC | |
| Time to restore DB | Measured | |
| Time to validate evidence objects | Measured | |
| Time to restore application service | Measured | |

Do not invent RPO/RTO targets. If no approved objectives exist, record measurements but mark objective acceptance INCOMPLETE and leave KV-007 open.

## 9. Cleanup and closure

- [ ] Isolated services stopped.
- [ ] Temporary credentials revoked.
- [ ] Temporary recovery database and disposable volumes destroyed under approved procedure.
- [ ] Downloaded encrypted backups and decrypted temporary files securely removed.
- [ ] Temporary secrets and passphrase files removed.
- [ ] No production resource was modified.
- [ ] Redacted logs and evidence artifacts were stored in an access-controlled location.
- [ ] Approver reviewed the complete evidence package.
- [ ] Defects were recorded as linked work items without overwriting this record.

## 10. Final decision

**PASS** is permitted only when every applicable restore, database/RLS, evidence-object, application, cleanup, approved RPO/RTO, and independent-approval criterion is evidenced.

- **PASS:** every required check succeeded and the approver accepted the evidence.
- **FAIL:** a safety violation, checksum mismatch, restore failure, RLS failure, missing required evidence object, or failed application acceptance occurred.
- **INCOMPLETE:** execution was not performed or any required evidence, approved objective, cleanup proof, or approval is missing.

| Decision field | Value |
|---|---|
| Final result | NOT RUN / INCOMPLETE / FAIL / PASS |
| Operator sign-off | |
| Approver sign-off | |
| Evidence package URI / reference | |
| Linked defects / follow-up work items | |
| Closure date (UTC) | |

**KV-007 remains BLOCKED until a complete PASS record is independently reviewed and linked from the engineering work register.**

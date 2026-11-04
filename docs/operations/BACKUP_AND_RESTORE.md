# KRAVIGIL — Backup and Restore Runbook

## Scope and recovery objective

KRAVIGIL creates encrypted PostgreSQL custom-format backups and stores them in the private MinIO backup bucket. The production deployment configures bucket versioning and replication to an off-host HTTPS S3-compatible target.

The default configuration is a daily backup interval and a 30-day lifecycle retention window. Set these values deliberately against the required recovery point objective (RPO), recovery time objective (RTO), legal retention rules, and available storage. A successful backup job is not proof of recoverability: perform isolated restore drills and retain their results.

## Backup creation

The Compose backup service runs `infrastructure/backup/pg_backup.py` repeatedly. The image entrypoint waits `BACKUP_INTERVAL_SECONDS` (default 86400 seconds) between attempts. Each successful run:

1. Creates a PostgreSQL custom-format dump using `pg_dump`.
2. Validates the dump directory with `pg_restore --list`.
3. Encrypts the dump using GPG symmetric AES-256 with the configured `BACKUP_ENCRYPTION_KEY`.
4. Calculates SHA-256 over the encrypted artifact.
5. Uploads the encrypted dump and a `.sha256` sidecar to `MINIO_BACKUP_BUCKET`.
6. Updates `/tmp/last-success`, which is used by the Compose health check.

A failed attempt is logged and retried at the next interval. Check backup-container logs and health, not just container uptime:

```bash
docker compose -f infrastructure/docker-compose.yml \
  -f infrastructure/docker-compose.prod.yml \
  -f infrastructure/docker-compose.backup.yml ps backup

docker compose -f infrastructure/docker-compose.yml \
  -f infrastructure/docker-compose.prod.yml \
  -f infrastructure/docker-compose.backup.yml logs --since=48h backup
```

## Replication and retention

`scripts/deploy_prod.sh` invokes `infrastructure/minio/replicate.sh` and `verify_replication.sh`. The replication setup enables versioning on source and target buckets, replicates backup objects to the remote bucket, and configures MinIO lifecycle rules using `BACKUP_RETENTION_DAYS` (default 30) for current and noncurrent backup versions. Backup delete markers are deliberately not replicated, so source-side deletion does not immediately remove the remote recovery copy. The remote bucket's own lifecycle still limits its retention window.

After deployment or any retention-policy change, inspect both source and target lifecycle rules and replication status. Do not assume an existing rule was updated merely because the setup script completed; compare the effective expiry and noncurrent-version expiry values with the configured retention period. Preserve command output as operational evidence.

Keep `BACKUP_ENCRYPTION_KEY` in an independent secrets manager or offline escrow. A backup and its encryption key must not depend on the same host, account, or storage failure domain. Do not store the passphrase alongside the encrypted dump.

## Restore a backup into an isolated database

**Never run a restore drill against the live production database.** The restore utility refuses a target database whose name equals `DB_NAME` and requires `RESTORE_CONFIRMATION` to match the target database name exactly. It uses a single PostgreSQL transaction and stops on the first restore error.

### 1. Select and verify the backup object

From a host with authorized access to the source or off-host recovery bucket, list backup objects and select a specific `.dump.gpg` key:

```bash
mc ls --recursive source/kravigil-backups/postgresql/
mc ls --recursive target/kravigil-backups/postgresql/
```

The selected backup must have a matching `.sha256` sidecar. Use the remote target when validating disaster recovery from loss or compromise of the primary host or MinIO deployment.

### 2. Create a separate empty recovery database

Create the recovery database on a PostgreSQL instance isolated from production. For example, using a dedicated recovery administrator:

```bash
createdb --host "$RESTORE_DB_HOST" --port "$RESTORE_DB_PORT" \
  --username "$RESTORE_DB_ADMIN" "$RESTORE_DB_NAME"
```

Use a unique database name that is not the production `DB_NAME`. Restrict network access to the recovery operator and application components needed for validation.

### 3. Run the verified restore utility

Run `infrastructure/backup/pg_restore.py` from a trusted recovery host with Python 3.11, the `minio` Python package, GnuPG, and PostgreSQL client tools installed. Configure these environment variables without placing secrets in source control:

- `BACKUP_OBJECT_KEY`: exact object key selected in step 1, beginning with `postgresql/` and ending in `.dump.gpg`.
- `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_BACKUP_BUCKET`, and `MINIO_SECURE`: credentials and endpoint for the bucket holding the selected backup (prefer the off-host replica for a disaster-recovery drill).
- `BACKUP_ENCRYPTION_KEY`: independently escrowed encryption passphrase.
- `DB_NAME`: production database name, used only as a safety guard.
- `RESTORE_DB_HOST`, `RESTORE_DB_PORT`, `RESTORE_DB_NAME`, `RESTORE_DB_USER`, and `RESTORE_DB_PASSWORD`: the isolated recovery database connection.
- `RESTORE_CONFIRMATION`: must exactly equal `RESTORE_DB_NAME`.

Then execute:

```bash
python infrastructure/backup/pg_restore.py
```

The utility downloads the dump and checksum sidecar, validates the encrypted artifact's SHA-256, decrypts it using a mode-0600 temporary passphrase file, validates the PostgreSQL archive, and restores it with `--exit-on-error --single-transaction --clean --if-exists`. It does not print credentials or passphrases.

### 4. Validate the restored system

At minimum:

1. Confirm the restore process exited successfully and the expected tables, migration version, organizations, users, scans, findings, and evidence metadata exist.
2. Verify representative row counts and referential integrity against the backup's expected state.
3. Verify that RLS policies and application roles are present and that cross-tenant reads remain denied.
4. Verify evidence objects are available from the corresponding object-store replica and that downloaded contents match their stored SHA-256 values.
5. Start the application only in an isolated recovery/staging environment and run its health, login/MFA, scan, report, and evidence workflows.
6. Record the backup key, backup timestamp, restore start/end times, checksum result, migration version, validation outcomes, and measured RTO.

A PostgreSQL dump does not include MinIO evidence objects. Database recovery and object-store recovery must be validated together.

## Operational acceptance checklist

- [ ] Daily backup completes and the backup service remains healthy across at least two scheduled intervals.
- [ ] Encrypted dump and checksum sidecar are present in the source bucket.
- [ ] Replication status is healthy and the same backup is visible in the off-host target.
- [ ] Source and target lifecycle rules match the approved current-version and noncurrent-version retention policy.
- [ ] A restore from the off-host target succeeds in an isolated database.
- [ ] Restored application data, RLS, and evidence object hashes pass validation.
- [ ] Measured RPO/RTO meet the service's approved objectives.
- [ ] Encryption key escrow and recovery access are tested independently of the production host.

Do not declare production readiness until a real off-host restore drill has passed. CI and a healthy backup container are necessary but insufficient evidence of recoverability.

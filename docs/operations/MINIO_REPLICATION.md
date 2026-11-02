# MinIO Cross-Cluster Replication

## Overview
KRAVIGIL replicates evidence data from a primary MinIO instance to a secondary (target) MinIO instance for disaster recovery. This ensures evidence integrity even if the primary cluster is destroyed.

## Prerequisites
1. Two MinIO instances running (source and target).
2. Both instances accessible via the `infrastructure_data_plane` Docker network.
3. `mc` (MinIO Client) available (via `minio/mc` Docker image).
4. Target bucket must exist (or the script creates it).

## Configuration

Add the following variables to your `.env` file:

```env
MINIO_SOURCE_URL=http://minio:9000
MINIO_TARGET_URL=http://target-minio:9000
MINIO_SOURCE_USER=kravigil_minio
MINIO_SOURCE_PASSWORD=kravigil_minio_secure_pass
MINIO_TARGET_USER=kravigil_minio
MINIO_TARGET_PASSWORD=kravigil_minio_secure_pass
MINIO_BUCKET=kravigil-evidence
```

## Usage

### 1. Configure Replication
```bash
make replicate-minio
```

### 2. Verify Replication
```bash
make verify-replication
```

### 3. Manual Verification
```bash
# List replication rules
mc replicate ls source/kravigil-evidence

# Check replication status
mc admin replicate status source kravigil-evidence
```

## How It Works
1. Both source and target buckets have versioning enabled (required by MinIO replication).
2. A replication rule (`replicate-all` by default) is created on the source.
3. New objects and delete markers are automatically replicated to the target.
4. Existing objects are copied during the initial sync.

## Troubleshooting

### "Bucket does not exist"
```bash
mc mb source/kravigil-evidence
mc mb target/kravigil-evidence
```

### "Replication rule already exists"
The script is idempotent. It will print a warning but not fail. Use `mc replicate ls` to verify.

### "Permission denied"
Ensure the `MINIO_SOURCE_USER` and `MINIO_TARGET_USER` have `admin:CreateReplication` permissions on the buckets.

## Security Notes
- **Never commit `.env` to Git**. It is already in `.gitignore`.
- **Use distinct credentials** for source and target in production (not the same user/password).
- **Enable TLS** (`https://`) for both MinIO instances in production.
- **Rotate credentials** regularly via your secrets manager.

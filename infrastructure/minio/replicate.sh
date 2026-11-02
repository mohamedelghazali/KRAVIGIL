
#!/bin/bash

set -euo pipefail

# MinIO replication configuration
SOURCE_ALIAS="kravigil-src"
TARGET_ALIAS="kravigil-tgt"

SOURCE_URL="${MINIO_SOURCE_URL:-http://localhost:9000}"
TARGET_URL="${MINIO_TARGET_URL:-http://target-minio:9000}"

SOURCE_ACCESS_KEY="${MINIO_SOURCE_USER:?MINIO_SOURCE_USER is required}"
SOURCE_SECRET_KEY="${MINIO_SOURCE_PASSWORD:?MINIO_SOURCE_PASSWORD is required}"

TARGET_ACCESS_KEY="${MINIO_TARGET_USER:?MINIO_TARGET_USER is required}"
TARGET_SECRET_KEY="${MINIO_TARGET_PASSWORD:?MINIO_TARGET_PASSWORD is required}"

BUCKET_NAME="${MINIO_BUCKET:-kravigil-evidence}"

echo "[*] Configuring MinIO aliases..."

mc alias set "$SOURCE_ALIAS" "$SOURCE_URL" \
    "$SOURCE_ACCESS_KEY" "$SOURCE_SECRET_KEY"

mc alias set "$TARGET_ALIAS" "$TARGET_URL" \
    "$TARGET_ACCESS_KEY" "$TARGET_SECRET_KEY"

echo "[*] Enabling bucket versioning..."

mc version enable "$SOURCE_ALIAS/$BUCKET_NAME"
mc version enable "$TARGET_ALIAS/$BUCKET_NAME"

echo "[*] Configuring bucket replication..."

mc replicate add "$SOURCE_ALIAS/$BUCKET_NAME" \
    --remote-bucket "$TARGET_ALIAS/$BUCKET_NAME" \
    --priority 1 \
    --replicate "delete,delete-marker,existing-objects"

echo "[+] MinIO replication configuration completed."
echo "[*] Check replication status using:"
echo "mc replicate ls $SOURCE_ALIAS/$BUCKET_NAME"

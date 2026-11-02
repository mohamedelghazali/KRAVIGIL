#!/bin/bash

set -e

REQUIRED_VARS=(
    "MINIO_SOURCE_URL"
    "MINIO_TARGET_URL"
    "MINIO_SOURCE_USER"
    "MINIO_SOURCE_PASSWORD"
    "MINIO_TARGET_USER"
    "MINIO_TARGET_PASSWORD"
    "MINIO_BUCKET"
)

echo "[*] Validating required environment variables..."
for VAR in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!VAR}" ]; then
        echo "[-] Missing required environment variable: ${VAR}"
        exit 1
    fi
done

echo "[*] Setting up MinIO Cross-Cluster Replication..."
echo "[*] Source: ${MINIO_SOURCE_URL}"
echo "[*] Target: ${MINIO_TARGET_URL}"
echo "[*] Bucket: ${MINIO_BUCKET}"

docker run --rm \
    --network infrastructure_data_plane \
    -e MC_HOST_source="http://${MINIO_SOURCE_USER}:${MINIO_SOURCE_PASSWORD}@${MINIO_SOURCE_URL}" \
    -e MC_HOST_target="http://${MINIO_TARGET_USER}:${MINIO_TARGET_PASSWORD}@${MINIO_TARGET_URL}" \
    -e BUCKET="${MINIO_BUCKET}" \
    minio/mc /bin/sh -c '
        set -e
        echo "[+] Configuring aliases..."
        mc alias set source "$MC_HOST_source"
        mc alias set target "$MC_HOST_target"

        echo "[+] Enabling versioning on source bucket..."
        mc version enable "source/$BUCKET" || echo "[!] Versioning already enabled or failed"

        echo "[+] Enabling versioning on target bucket..."
        mc version enable "target/$BUCKET" || echo "[!] Versioning already enabled or failed"

        echo "[+] Creating replication rule..."
        mc replicate add "source/$BUCKET" \
            --remote-bucket "target/$BUCKET" \
            --priority 1 \
            --replicate "delete,delete-marker,existing-objects" \
            || echo "[!] Replication rule may already exist"

        echo "[+] Replication status:"
        mc replicate ls "source/$BUCKET"
    '

echo "[+] MinIO Replication configured successfully."
echo "[*] Verify replication: mc admin replicate status source/${MINIO_BUCKET}"

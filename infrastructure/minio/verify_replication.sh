#!/bin/bash

set -e

REQUIRED_VARS=(
    "MINIO_SOURCE_URL"
    "MINIO_SOURCE_USER"
    "MINIO_SOURCE_PASSWORD"
    "MINIO_BUCKET"
)

echo "[*] Validating required environment variables..."
for VAR in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!VAR}" ]; then
        echo "[-] Missing required environment variable: ${VAR}"
        exit 1
    fi
done

docker run --rm \
    --network infrastructure_data_plane \
    -e MC_HOST_source="http://${MINIO_SOURCE_USER}:${MINIO_SOURCE_PASSWORD}@${MINIO_SOURCE_URL}" \
    -e BUCKET="${MINIO_BUCKET}" \
    minio/mc /bin/sh -c '
        set -e
        mc alias set source "$MC_HOST_source"
        
        echo "[*] Replication Rule List:"
        mc replicate ls "source/$BUCKET"
        
        echo ""
        echo "[*] Replication Status:"
        mc admin replicate status source "$BUCKET"
        
        echo ""
        echo "[*] Object Count (Source):"
        mc ls --recursive --summarize "source/$BUCKET" | tail -n 1
    '

echo "[+] Verification complete."

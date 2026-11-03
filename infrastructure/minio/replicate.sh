#!/usr/bin/env bash
set -Eeuo pipefail

: "${MINIO_USER:?MINIO_USER is required for the source MinIO account}"
: "${MINIO_PASSWORD:?MINIO_PASSWORD is required for the source MinIO account}"
: "${MINIO_TARGET_USER:?MINIO_TARGET_USER is required for the target MinIO account}"
: "${MINIO_TARGET_PASSWORD:?MINIO_TARGET_PASSWORD is required for the target MinIO account}"
: "${MINIO_BUCKET:=kravigil-evidence}"
: "${MINIO_BACKUP_BUCKET:=kravigil-backups}"
: "${MINIO_SOURCE_URL:=http://minio:9000}"
: "${MINIO_TARGET_URL:=http://target-minio:9000}"

NETWORK="$(docker network ls --filter label=com.docker.compose.network=data_plane --format '{{.Name}}' | head -n 1)"
if [[ -z "$NETWORK" ]]; then
  echo "ERROR: Could not find the Compose data_plane network." >&2
  exit 1
fi

docker run --rm \
  --network "$NETWORK" \
  -e MC_HOST_source="http://${MINIO_USER}:${MINIO_PASSWORD}@${MINIO_SOURCE_URL#http://}" \
  -e MC_HOST_target="http://${MINIO_TARGET_USER}:${MINIO_TARGET_PASSWORD}@${MINIO_TARGET_URL#http://}" \
  -e EVIDENCE_BUCKET="$MINIO_BUCKET" \
  -e BACKUP_BUCKET="$MINIO_BACKUP_BUCKET" \
  minio/mc:RELEASE.2025-08-13T08-35-41Z /bin/sh -ec '
    mc alias set source "$MC_HOST_source"
    mc alias set target "$MC_HOST_target"

    for BUCKET in "$EVIDENCE_BUCKET" "$BACKUP_BUCKET"; do
      echo "Configuring versioning and replication for $BUCKET"
      mc mb --ignore-existing "source/$BUCKET"
      mc mb --ignore-existing "target/$BUCKET"
      mc version enable "source/$BUCKET"
      mc version enable "target/$BUCKET"
      if ! mc replicate ls "source/$BUCKET" | grep -q "target/$BUCKET"; then
        mc replicate add "source/$BUCKET" \
          --remote-bucket "target/$BUCKET" \
          --priority 1 \
          --replicate "delete,delete-marker,existing-objects"
      fi
      mc replicate status "source/$BUCKET"
    done
  '

echo "MinIO versioning and replication rules configured."

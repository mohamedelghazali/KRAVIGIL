#!/usr/bin/env bash
set -Eeuo pipefail

: "${MINIO_USER:?MINIO_USER is required}"
: "${MINIO_PASSWORD:?MINIO_PASSWORD is required}"
: "${MINIO_TARGET_USER:?MINIO_TARGET_USER is required}"
: "${MINIO_TARGET_PASSWORD:?MINIO_TARGET_PASSWORD is required}"
: "${MINIO_BUCKET:=kravigil-evidence}"
: "${MINIO_BACKUP_BUCKET:=kravigil-backups}"

NETWORK="$(docker network ls --filter label=com.docker.compose.network=data_plane --format '{{.Name}}' | head -n 1)"
if [[ -z "$NETWORK" ]]; then
  echo "ERROR: Could not find the Compose data_plane network." >&2
  exit 1
fi

docker run --rm \
  --network "$NETWORK" \
  -e MC_HOST_source="http://${MINIO_USER}:${MINIO_PASSWORD}@minio:9000" \
  -e MC_HOST_target="http://${MINIO_TARGET_USER}:${MINIO_TARGET_PASSWORD}@target-minio:9000" \
  -e EVIDENCE_BUCKET="$MINIO_BUCKET" \
  -e BACKUP_BUCKET="$MINIO_BACKUP_BUCKET" \
  minio/mc:RELEASE.2025-08-13T08-35-41Z /bin/sh -ec '
    mc alias set source "$MC_HOST_source"
    mc alias set target "$MC_HOST_target"
    for BUCKET in "$EVIDENCE_BUCKET" "$BACKUP_BUCKET"; do
      echo "=== $BUCKET ==="
      mc replicate ls "source/$BUCKET"
      mc replicate status "source/$BUCKET"
      mc ilm rule ls --json "source/$BUCKET"
      mc ilm rule ls --json "target/$BUCKET"
      mc ls --recursive --summarize "source/$BUCKET" | tail -n 1
    done
  '

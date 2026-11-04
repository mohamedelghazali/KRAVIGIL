#!/usr/bin/env bash
set -Eeuo pipefail

: "${MINIO_USER:?MINIO_USER is required for the source storage account}"
: "${MINIO_PASSWORD:?MINIO_PASSWORD is required for the source storage account}"
: "${MINIO_TARGET_USER:?MINIO_TARGET_USER is required for the off-host target}"
: "${MINIO_TARGET_PASSWORD:?MINIO_TARGET_PASSWORD is required for the off-host target}"
: "${MINIO_SOURCE_URL:=http://minio:9000}"
: "${MINIO_TARGET_URL:?MINIO_TARGET_URL must be an external HTTPS S3-compatible endpoint}"

if [[ "$MINIO_TARGET_URL" != https://* ]]; then
  echo "ERROR: MINIO_TARGET_URL must use HTTPS." >&2
  exit 1
fi

source_authority="${MINIO_SOURCE_URL#*://}"
target_authority="${MINIO_TARGET_URL#https://}"
source_host="${source_authority%%[:/]*}"
target_host="${target_authority%%[:/]*}"
target_host="${target_host,,}"

case "$target_host" in
  ""|localhost|localhost.localdomain|minio|target-minio|host.docker.internal|gateway.docker.internal|127.*|0.0.0.0|change_me*)
    echo "ERROR: MINIO_TARGET_URL must identify a remote storage endpoint, not a local Compose service or placeholder." >&2
    exit 1
    ;;
esac
case "$target_authority" in
  \[::1\]*|\[::\]*) echo "ERROR: MINIO_TARGET_URL cannot use a loopback/unspecified IPv6 address." >&2; exit 1 ;;
esac
if [[ "$target_host" == "${source_host,,}" ]]; then
  echo "ERROR: source and replication target must use different hostnames." >&2
  exit 1
fi
if [[ "$target_authority" == */* || "$target_authority" == *\?* || "$target_authority" == *\#* ]]; then
  echo "ERROR: MINIO_TARGET_URL must be an endpoint origin without a path, query or fragment." >&2
  exit 1
fi

COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-kravigil}"
DATA_NETWORK="${COMPOSE_PROJECT_NAME}_data_plane"
EGRESS_NETWORK="${COMPOSE_PROJECT_NAME}_control_plane"
MC_IMAGE="minio/mc:RELEASE.2025-08-13T08-35-41Z"

docker network inspect "$DATA_NETWORK" >/dev/null
docker network inspect "$EGRESS_NETWORK" >/dev/null

mc_host() {
  local url="$1" username="$2" password="$3"
  local scheme="${url%%://*}" authority="${url#*://}"
  if [[ "$scheme" != "http" && "$scheme" != "https" ]] || [[ "$authority" == */* ]]; then
    echo "ERROR: invalid S3 endpoint URL: $url" >&2
    return 1
  fi
  printf '%s://%s:%s@%s' "$scheme" "$username" "$password" "$authority"
}

run_mc() {
  local container_id status=0
  container_id="$(docker create \
    --network "$EGRESS_NETWORK" \
    -e "MC_HOST_source=$(mc_host "$MINIO_SOURCE_URL" "$MINIO_USER" "$MINIO_PASSWORD")" \
    -e "MC_HOST_target=$(mc_host "$MINIO_TARGET_URL" "$MINIO_TARGET_USER" "$MINIO_TARGET_PASSWORD")" \
    -e "EVIDENCE_BUCKET=${MINIO_BUCKET:-kravigil-evidence}" \
    -e "BACKUP_BUCKET=${MINIO_BACKUP_BUCKET:-kravigil-backups}" \
    -e "BACKUP_RETENTION_DAYS=${BACKUP_RETENTION_DAYS:-30}" \
    "$MC_IMAGE" "$@")"
  if ! docker network connect "$DATA_NETWORK" "$container_id"; then
    docker rm -f "$container_id" >/dev/null 2>&1 || true
    return 1
  fi
  docker start -a "$container_id" || status=$?
  docker rm -f "$container_id" >/dev/null 2>&1 || true
  return "$status"
}

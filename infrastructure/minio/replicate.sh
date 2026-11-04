#!/usr/bin/env bash
set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=mc_network.sh
source "$SCRIPT_DIR/mc_network.sh"

: "${MINIO_BUCKET:=kravigil-evidence}"
: "${MINIO_BACKUP_BUCKET:=kravigil-backups}"
: "${BACKUP_RETENTION_DAYS:=30}"

run_mc /bin/sh -ec '
  mc alias set source "$MC_HOST_source"
  mc alias set target "$MC_HOST_target"

  for BUCKET in "$EVIDENCE_BUCKET" "$BACKUP_BUCKET"; do
    echo "Configuring versioning and replication for $BUCKET"
    mc mb --ignore-existing "source/$BUCKET"
    mc mb --ignore-existing "target/$BUCKET"
    mc version enable "source/$BUCKET"
    mc version enable "target/$BUCKET"
    if ! mc replicate ls "source/$BUCKET" | grep -q "target/$BUCKET"; then
      if [[ "$BUCKET" == "$BACKUP_BUCKET" ]]; then
        # Preserve backup versions on the recovery target even if the source
        # bucket or its credentials are compromised.
        REPLICATION_FLAGS="existing-objects"
      else
        # Evidence deletions must propagate to the replica; provider-side
        # retention/Object Lock must still protect versions during the policy window.
        REPLICATION_FLAGS="delete,delete-marker,existing-objects"
      fi
      mc replicate add "source/$BUCKET" \
        --remote-bucket "target/$BUCKET" \
        --priority 1 \
        --replicate "$REPLICATION_FLAGS"
    fi
    mc replicate status "source/$BUCKET"
  done

  for ALIAS in source target; do
    RULES="$(mc --json ilm rule ls "$ALIAS/$BACKUP_BUCKET" 2>/dev/null || true)"
    if ! printf "%s" "$RULES" | grep -q "\"expireDays\":"; then
      mc ilm rule add --expire-days "$BACKUP_RETENTION_DAYS" \
        --noncurrent-expire-days "$BACKUP_RETENTION_DAYS" "$ALIAS/$BACKUP_BUCKET"
    fi
    if ! printf "%s" "$RULES" | grep -q "\"expireDeleteMarker\":true"; then
      mc ilm rule add --expire-delete-marker "$ALIAS/$BACKUP_BUCKET"
    fi
  done
' 
echo "S3-compatible bucket versioning and replication rules configured."

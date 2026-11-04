#!/usr/bin/env bash
set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=mc_network.sh
source "$SCRIPT_DIR/mc_network.sh"

: "${MINIO_BUCKET:=kravigil-evidence}"
: "${MINIO_BACKUP_BUCKET:=kravigil-backups}"

run_mc /bin/sh -ec '
  mc alias set source "$MC_HOST_source"
  mc alias set target "$MC_HOST_target"
  for BUCKET in "$EVIDENCE_BUCKET" "$BACKUP_BUCKET"; do
    echo "=== $BUCKET ==="
    mc replicate ls "source/$BUCKET"
    mc replicate status "source/$BUCKET"
    mc --json ilm rule ls "source/$BACKUP_BUCKET"
    mc --json ilm rule ls "target/$BACKUP_BUCKET"
    echo "Source object summary:"
    mc ls --recursive --summarize "source/$BUCKET" | tail -n 1
    echo "Target object summary:"
    mc ls --recursive --summarize "target/$BUCKET" | tail -n 1
  done
'

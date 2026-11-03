#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env from .env.example."
  echo "Edit .env with unique production secrets, configure the TLS files and domain, then run this script again."
  exit 1
fi

exec "$ROOT_DIR/scripts/deploy_prod.sh"

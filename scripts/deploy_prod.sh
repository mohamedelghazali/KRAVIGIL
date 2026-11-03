#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

BASE_COMPOSE=(-f infrastructure/docker-compose.yml -f infrastructure/docker-compose.prod.yml)

if [[ ! -f .env ]]; then
  echo "ERROR: .env is missing. Copy .env.example and configure real secrets." >&2
  exit 1
fi

set -a
# shellcheck disable=SC1091
source ./.env
set +a

require_secret() {
  local name="$1"
  local min_length="$2"
  local value="${!name:-}"
  if [[ -z "$value" || "$value" == CHANGE_ME* || "${#value}" -lt "$min_length" ]]; then
    echo "ERROR: $name must be set to a unique value of at least $min_length characters." >&2
    exit 1
  fi
}

for name in SECRET_KEY DB_PASSWORD REDIS_PASSWORD MINIO_PASSWORD GRAFANA_PASSWORD KRAVIGIL_ENGINE_AUTH_TOKEN ADMIN_PASSWORD SMTP_USERNAME SMTP_PASSWORD MINIO_SOURCE_PASSWORD MINIO_TARGET_PASSWORD; do
  case "$name" in
    SECRET_KEY|KRAVIGIL_ENGINE_AUTH_TOKEN) require_secret "$name" 64 ;;
    DB_PASSWORD|REDIS_PASSWORD|MINIO_PASSWORD|GRAFANA_PASSWORD|SMTP_PASSWORD|MINIO_SOURCE_PASSWORD|MINIO_TARGET_PASSWORD) require_secret "$name" 32 ;;
    *) require_secret "$name" 16 ;;
  esac
done

for name in MINIO_USER MINIO_SOURCE_USER MINIO_TARGET_USER SMTP_HOST SMTP_FROM_ADDRESS ADMIN_EMAIL FRONTEND_URL; do
  if [[ -z "${!name:-}" || "${!name}" == CHANGE_ME* ]]; then
    echo "ERROR: $name must be configured in .env." >&2
    exit 1
  fi
done

# Passwords embedded in DATABASE_URL / REDIS_URL must be URL-safe.
for name in DB_PASSWORD REDIS_PASSWORD; do
  if [[ ! "${!name}" =~ ^[A-Za-z0-9_-]+$ ]]; then
    echo "ERROR: $name may contain only letters, digits, underscore and hyphen." >&2
    exit 1
  fi
done

case "$FRONTEND_URL" in
  https://*) ;;
  *) echo "ERROR: FRONTEND_URL must use HTTPS in production." >&2; exit 1 ;;
esac
DOMAIN="${FRONTEND_URL#https://}"
DOMAIN="${DOMAIN%%/*}"
if ! grep -Fq "server_name $DOMAIN;" infrastructure/nginx/nginx.prod.conf; then
  echo "ERROR: nginx.prod.conf server_name must match $DOMAIN." >&2
  exit 1
fi
if [[ ! -s "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" || ! -s "/etc/letsencrypt/live/$DOMAIN/privkey.pem" ]]; then
  echo "ERROR: Let's Encrypt certificate files for $DOMAIN are missing under /etc/letsencrypt." >&2
  exit 1
fi

CERT_DIR="infrastructure/certs/network-engine"
for file in "$CERT_DIR/server.crt" "$CERT_DIR/server.key" "$CERT_DIR/ca.crt"; do
  if [[ ! -s "$file" ]]; then
    echo "ERROR: required gRPC TLS file is missing or empty: $file" >&2
    exit 1
  fi
done

if command -v openssl >/dev/null 2>&1; then
  openssl x509 -in "$CERT_DIR/server.crt" -noout >/dev/null
  openssl pkey -in "$CERT_DIR/server.key" -noout >/dev/null
  if ! openssl x509 -in "$CERT_DIR/server.crt" -noout -ext subjectAltName | grep -q 'DNS:network_engine'; then
    echo "ERROR: gRPC server certificate must include DNS:network_engine in subjectAltName." >&2
    exit 1
  fi
fi

docker compose version >/dev/null
docker compose "${BASE_COMPOSE[@]}" config --quiet

echo "[1/6] Building production images..."
docker compose "${BASE_COMPOSE[@]}" build

echo "[2/6] Starting data services and the TLS-protected network engine..."
docker compose "${BASE_COMPOSE[@]}" up -d db redis minio target-minio network_engine

echo "[3/6] Starting backend after healthy dependencies..."
docker compose "${BASE_COMPOSE[@]}" up -d backend

echo "[4/6] Applying database migrations..."
docker compose "${BASE_COMPOSE[@]}" exec -T backend alembic upgrade head

echo "[5/6] Ensuring the initial administrator exists..."
docker compose "${BASE_COMPOSE[@]}" exec -T backend python /app/scripts/seed_db.py

echo "[6/6] Starting remaining services..."
docker compose "${BASE_COMPOSE[@]}" up -d worker frontend nginx prometheus grafana

echo "Deployment commands completed. Checking application health..."
curl --fail --silent --show-error "${FRONTEND_URL%/}/api/v1/system/health"
echo
docker compose "${BASE_COMPOSE[@]}" ps
echo "KRAVIGIL deployment completed. Review service health and logs before opening access to users."

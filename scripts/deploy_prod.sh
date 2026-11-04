#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
mkdir -p workspace
export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-kravigil}"

BASE_COMPOSE=(-f infrastructure/docker-compose.yml -f infrastructure/docker-compose.prod.yml -f infrastructure/docker-compose.backup.yml)

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

for name in SECRET_KEY DB_PASSWORD APP_DB_PASSWORD BACKUP_ENCRYPTION_KEY REDIS_PASSWORD MINIO_PASSWORD GRAFANA_PASSWORD KRAVIGIL_ENGINE_AUTH_TOKEN ADMIN_PASSWORD SMTP_USERNAME SMTP_PASSWORD MINIO_TARGET_PASSWORD; do
  case "$name" in
    SECRET_KEY|KRAVIGIL_ENGINE_AUTH_TOKEN) require_secret "$name" 64 ;;
    DB_PASSWORD|APP_DB_PASSWORD|BACKUP_ENCRYPTION_KEY|REDIS_PASSWORD|MINIO_PASSWORD|GRAFANA_PASSWORD|SMTP_PASSWORD|MINIO_SOURCE_PASSWORD|MINIO_TARGET_PASSWORD) require_secret "$name" 32 ;;
    *) require_secret "$name" 16 ;;
  esac
done

for name in MINIO_USER MINIO_TARGET_USER SMTP_HOST SMTP_FROM_ADDRESS ADMIN_EMAIL FRONTEND_URL MINIO_TARGET_URL; do
  if [[ -z "${!name:-}" || "${!name}" == CHANGE_ME* ]]; then
    echo "ERROR: $name must be configured in .env." >&2
    exit 1
  fi
done

# Passwords embedded in DATABASE_URL / REDIS_URL must be URL-safe.
for name in DB_PASSWORD APP_DB_PASSWORD REDIS_PASSWORD; do
  if [[ ! "${!name}" =~ ^[A-Za-z0-9_-]+$ ]]; then
    echo "ERROR: $name may contain only letters, digits, underscore and hyphen." >&2
    exit 1
  fi
done

case "$MINIO_TARGET_URL" in
  https://*) ;;
  *) echo "ERROR: MINIO_TARGET_URL must be an off-host HTTPS S3-compatible endpoint." >&2; exit 1 ;;
esac
TARGET_AUTHORITY="${MINIO_TARGET_URL#https://}"
TARGET_HOST="${TARGET_AUTHORITY%%[:/]*}"
case "${TARGET_HOST,,}" in
  ""|localhost|minio|target-minio|127.0.0.1|0.0.0.0|change_me*)
    echo "ERROR: MINIO_TARGET_URL must point to a configured remote storage service, not a local Compose service or placeholder." >&2
    exit 1
    ;;
esac
if [[ "$TARGET_AUTHORITY" == */* || "$TARGET_AUTHORITY" == *\?* || "$TARGET_AUTHORITY" == *\#* ]]; then
  echo "ERROR: MINIO_TARGET_URL must be an endpoint origin without path/query/fragment." >&2
  exit 1
fi
SOURCE_AUTHORITY="${MINIO_SOURCE_URL#*://}"
SOURCE_HOST="${SOURCE_AUTHORITY%%[:/]*}"
if [[ "${TARGET_HOST,,}" == "${SOURCE_HOST,,}" ]]; then
  echo "ERROR: source and replication target must use different hostnames." >&2
  exit 1
fi
case "${TARGET_HOST,,}" in
  127.*|host.docker.internal|gateway.docker.internal|localhost.localdomain)
    echo "ERROR: MINIO_TARGET_URL cannot point back to the local host." >&2
    exit 1
    ;;
esac

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
for file in "$CERT_DIR/server.crt" "$CERT_DIR/server.key" "$CERT_DIR/ca.crt" "$CERT_DIR/backend-client.crt" "$CERT_DIR/backend-client.key" "$CERT_DIR/worker-client.crt" "$CERT_DIR/worker-client.key"; do
  if [[ ! -s "$file" ]]; then
    echo "ERROR: required gRPC TLS file is missing or empty: $file" >&2
    exit 1
  fi
done

if ! command -v openssl >/dev/null 2>&1; then
  echo "ERROR: openssl is required to validate the network-engine mTLS certificate chain." >&2
  exit 1
fi

if command -v openssl >/dev/null 2>&1; then
  openssl x509 -in "$CERT_DIR/server.crt" -noout >/dev/null
  openssl pkey -in "$CERT_DIR/server.key" -noout >/dev/null
  openssl x509 -in "$CERT_DIR/ca.crt" -noout >/dev/null
  openssl verify -purpose sslserver -CAfile "$CERT_DIR/ca.crt" "$CERT_DIR/server.crt" >/dev/null
  for identity in backend worker; do
    openssl x509 -in "$CERT_DIR/$identity-client.crt" -noout >/dev/null
    openssl pkey -in "$CERT_DIR/$identity-client.key" -noout >/dev/null
    openssl verify -purpose sslclient -CAfile "$CERT_DIR/ca.crt" "$CERT_DIR/$identity-client.crt" >/dev/null
    if ! diff -q <(openssl x509 -in "$CERT_DIR/$identity-client.crt" -pubkey -noout) <(openssl pkey -in "$CERT_DIR/$identity-client.key" -pubout) >/dev/null; then
      echo "ERROR: gRPC $identity client certificate and private key do not match." >&2
      exit 1
    fi
    if ! openssl x509 -in "$CERT_DIR/$identity-client.crt" -noout -ext extendedKeyUsage | grep -q 'TLS Web Client Authentication'; then
      echo "ERROR: gRPC $identity client certificate must include clientAuth extendedKeyUsage." >&2
      exit 1
    fi
  done
  if ! diff -q <(openssl x509 -in "$CERT_DIR/server.crt" -pubkey -noout) <(openssl pkey -in "$CERT_DIR/server.key" -pubout) >/dev/null; then
    echo "ERROR: gRPC server certificate and private key do not match." >&2
    exit 1
  fi
  if ! openssl x509 -in "$CERT_DIR/server.crt" -noout -ext subjectAltName | grep -q 'DNS:network_engine'; then
    echo "ERROR: gRPC server certificate must include DNS:network_engine in subjectAltName." >&2
    exit 1
  fi
  if ! openssl x509 -in "$CERT_DIR/server.crt" -noout -ext extendedKeyUsage | grep -q 'TLS Web Server Authentication'; then
    echo "ERROR: gRPC server certificate must include serverAuth extendedKeyUsage." >&2
    exit 1
  fi
fi

docker compose version >/dev/null
docker compose "${BASE_COMPOSE[@]}" config --quiet

echo "[1/8] Building production images..."
docker compose "${BASE_COMPOSE[@]}" build

echo "[2/8] Starting data services and the mTLS-protected network engine..."
docker compose "${BASE_COMPOSE[@]}" up -d --wait db redis minio network_engine

echo "[3/8] Configuring evidence and backup replication..."
bash infrastructure/minio/replicate.sh
bash infrastructure/minio/verify_replication.sh

MIGRATION_DATABASE_URL="postgresql://kravigil_admin:${DB_PASSWORD}@db:5432/kravigil_db"
echo "[4/8] Applying database migrations with the restricted migration workflow..."
docker compose "${BASE_COMPOSE[@]}" run --rm --no-deps -e DATABASE_URL="$MIGRATION_DATABASE_URL" backend alembic upgrade head

echo "[5/8] Ensuring the initial administrator exists..."
docker compose "${BASE_COMPOSE[@]}" run --rm --no-deps -e DATABASE_URL="$MIGRATION_DATABASE_URL" backend python /app/scripts/seed_db.py

echo "[6/8] Provisioning the non-superuser application database role..."
docker compose "${BASE_COMPOSE[@]}" exec -T db psql -v ON_ERROR_STOP=1 \
  -U kravigil_admin -d kravigil_db \
  -v app_user=kravigil_app -v app_password="$APP_DB_PASSWORD" -v admin_user=kravigil_admin <<'SQL'
SELECT format('CREATE ROLE %I LOGIN', :'app_user')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'app_user') \gexec
ALTER ROLE :"app_user" WITH LOGIN PASSWORD :'app_password'
  NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION;
GRANT CONNECT ON DATABASE kravigil_db TO :"app_user";
GRANT USAGE ON SCHEMA public TO :"app_user";
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO :"app_user";
GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO :"app_user";
ALTER DEFAULT PRIVILEGES FOR ROLE :"admin_user" IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO :"app_user";
ALTER DEFAULT PRIVILEGES FOR ROLE :"admin_user" IN SCHEMA public
  GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO :"app_user";
SQL

echo "[7/8] Starting the application with RLS-enforced credentials..."
docker compose "${BASE_COMPOSE[@]}" up -d backend worker frontend nginx prometheus grafana backup

echo "[8/8] Checking application health..."
HEALTH_RESPONSE="$(curl --fail --silent --show-error "${FRONTEND_URL%/}/api/v1/system/health")"
printf '%s\n' "$HEALTH_RESPONSE"
if ! grep -Eq '"status"[[:space:]]*:[[:space:]]*"ok"' <<< "$HEALTH_RESPONSE"; then
  echo "ERROR: API health endpoint reports degraded or unhealthy components." >&2
  exit 1
fi
docker compose "${BASE_COMPOSE[@]}" ps
echo "KRAVIGIL deployment health checks passed. Review service health and logs before opening access to users."

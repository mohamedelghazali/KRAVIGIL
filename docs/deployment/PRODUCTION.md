# KRAVIGIL Production Deployment Guide

## Prerequisites

- Linux host with Docker Engine and the Docker Compose v2 plugin
- Public DNS record for the application domain
- Valid HTTPS certificate for the application domain (Let's Encrypt files mounted at `/etc/letsencrypt`)
- PostgreSQL persistent storage and a tested off-host backup destination
- SMTP credentials for password-reset delivery
- At least 4 CPU cores, 16 GB RAM and 100 GB persistent storage; size resources against measured workload

## 1. Configure secrets

Copy `.env.example` to `.env`. Replace every `CHANGE_ME` value. Do not commit `.env`.

Generate URL-safe random secrets, for example:

```bash
openssl rand -hex 32
```

Use unique values for `SECRET_KEY`, `DB_PASSWORD`, `APP_DB_PASSWORD`, `BACKUP_ENCRYPTION_KEY`, `REDIS_PASSWORD`, `MINIO_PASSWORD`, `GRAFANA_PASSWORD`, `KRAVIGIL_ENGINE_AUTH_TOKEN`, SMTP credentials and the initial administrator password. The deployment script rejects empty or placeholder values and requires HTTPS.

Set:

- `FRONTEND_URL=https://your-real-domain.example`
- `ALLOWED_ORIGINS=["https://your-real-domain.example"]`
- `ADMIN_EMAIL` and a unique strong `ADMIN_PASSWORD`
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, and `SMTP_FROM_ADDRESS`
- `MINIO_USER`/`MINIO_PASSWORD` for the local primary object store, plus `MINIO_TARGET_URL=https://...`, `MINIO_TARGET_USER`, and `MINIO_TARGET_PASSWORD` for a remote S3-compatible replication target

`GEMINI_API_KEY` and `OTX_API_KEY` are optional. AI analysis requires Gemini; threat-intelligence synchronization requires OTX.

Cloud scans use the pinned Prowler CLI. Configure AWS credentials (or an appropriate workload credential provider), Azure service-principal variables, or a GCP service-account JSON file. Set `GOOGLE_APPLICATION_CREDENTIALS_HOST_PATH` to the absolute host path of the GCP JSON file. The worker mounts that file read-only.

## 2. Configure the network engine TLS identity

The C++ gRPC transport requires **mutual TLS (mTLS)** as well as the per-request engine token. The engine verifies client certificates against the internal CA; backend and worker verify the engine server certificate and present their own client certificates. The server certificate must identify the Compose DNS name `network_engine`.

Generate a private CA, a server certificate, and a separate client certificate. Keep the CA private key offline and never mount it into containers:

```bash
set -euo pipefail
umask 077
CERT_DIR=infrastructure/certs/network-engine
mkdir -p "$CERT_DIR"

# Internal CA (keep ca.key offline after signing).
openssl req -x509 -newkey rsa:3072 -nodes \
  -keyout "$CERT_DIR/ca.key" -out "$CERT_DIR/ca.crt" -days 3650 \
  -subj "/CN=KRAVIGIL Internal Engine CA" \
  -addext "basicConstraints=critical,CA:TRUE" \
  -addext "keyUsage=critical,keyCertSign,cRLSign"

# Server identity: the SAN is required for hostname verification.
openssl req -newkey rsa:3072 -nodes \
  -keyout "$CERT_DIR/server.key" -out "$CERT_DIR/server.csr" \
  -subj "/CN=network_engine" \
  -addext "subjectAltName=DNS:network_engine"
printf 'subjectAltName=DNS:network_engine\nextendedKeyUsage=serverAuth\nkeyUsage=critical,digitalSignature,keyEncipherment\n' > "$CERT_DIR/server.ext"
openssl x509 -req -in "$CERT_DIR/server.csr" -CA "$CERT_DIR/ca.crt" \
  -CAkey "$CERT_DIR/ca.key" -CAcreateserial -out "$CERT_DIR/server.crt" \
  -days 825 -sha256 -copy_extensions copy -extfile "$CERT_DIR/server.ext"

# Separate client identities let operators revoke backend and worker access independently.
for identity in backend worker; do
  openssl req -newkey rsa:3072 -nodes \
    -keyout "$CERT_DIR/$identity-client.key" \
    -out "$CERT_DIR/$identity-client.csr" \
    -subj "/CN=kravigil-$identity"
  printf 'extendedKeyUsage=clientAuth\nkeyUsage=critical,digitalSignature\n' > "$CERT_DIR/$identity-client.ext"
  openssl x509 -req -in "$CERT_DIR/$identity-client.csr" -CA "$CERT_DIR/ca.crt" \
    -CAkey "$CERT_DIR/ca.key" -CAcreateserial -out "$CERT_DIR/$identity-client.crt" \
    -days 825 -sha256 -copy_extensions copy -extfile "$CERT_DIR/$identity-client.ext"
done

# Verify the chains before the deployment script does its own checks.
openssl verify -purpose sslserver -CAfile "$CERT_DIR/ca.crt" "$CERT_DIR/server.crt"
for identity in backend worker; do
  openssl verify -purpose sslclient -CAfile "$CERT_DIR/ca.crt" "$CERT_DIR/$identity-client.crt"
done
sudo chown 10001:10001 "$CERT_DIR/server.key" "$CERT_DIR/backend-client.key" "$CERT_DIR/worker-client.key"
sudo chmod 0440 "$CERT_DIR/server.key" "$CERT_DIR/backend-client.key" "$CERT_DIR/worker-client.key"
chmod 0444 "$CERT_DIR/server.crt" "$CERT_DIR/backend-client.crt" "$CERT_DIR/worker-client.crt" "$CERT_DIR/ca.crt"
rm -f "$CERT_DIR"/*.csr "$CERT_DIR"/*.ext "$CERT_DIR"/*.srl
# Securely archive the CA private key offline, then remove it from the host.
```

The required runtime files are `ca.crt`, `server.crt`, `server.key`, `backend-client.crt`, `backend-client.key`, `worker-client.crt`, and `worker-client.key`. The CA private key must not remain on the production host. All certificate/key files are excluded from Git. Backend and worker receive distinct client keys read-only; the network engine receives the CA and server key read-only. Rotate or revoke each client identity independently by issuing a new certificate from the trusted CA and restarting the affected service.

Create authorized SAST source directories under `workspace/`. The worker mounts this directory read-only and rejects paths outside `/workspace`.

## 3. Configure HTTPS termination

Update all three occurrences of the placeholder domain in `infrastructure/nginx/nginx.prod.conf` to the exact domain in `FRONTEND_URL`. Ensure the matching files exist:

- `/etc/letsencrypt/live/your-real-domain.example/fullchain.pem`
- `/etc/letsencrypt/live/your-real-domain.example/privkey.pem`

The deployment script checks the configured NGINX server name and certificate files before building.

## 4. Deploy

From the repository root:

```bash
./scripts/go_live.sh
```

The script validates secrets and certificates, requires an off-host HTTPS S3-compatible replication target, builds images, starts healthy dependencies, configures and verifies replication for evidence and backup buckets, applies Alembic migrations with the database administrator, seeds the initial administrator, provisions a non-superuser `kravigil_app` role, and runs the API and workers with that role so PostgreSQL row-level security is actually enforced. It then starts the remaining services, including encrypted PostgreSQL backups, and checks the HTTPS system-health endpoint. The temporary replication client is attached to both the internal data network and the egress-enabled control network; the database/data network itself remains internal.

The script does not perform a production deployment from this chat. Run it on the intended host after reviewing the configuration.

## 5. Post-deployment acceptance

Before opening public access:

1. Confirm every container is healthy and inspect backend, worker, network-engine, database and NGINX logs.
2. Verify login, MFA challenge, refresh, logout, password reset email, session revocation and tenant isolation.
3. Run network, web, SAST and cloud scan workflows only against explicitly authorized targets.
4. Verify report generation, evidence upload/download, webhook delivery, metrics and Grafana provisioning.
5. Wait for the first encrypted PostgreSQL backup to finish and confirm the backup container is healthy. Verify MinIO replication for both evidence and backup buckets.
6. Restore a backup into an isolated PostgreSQL database: download the `.dump.gpg` object and its `.sha256` sidecar, run `sha256sum -c`, decrypt with `gpg --batch --pinentry-mode loopback --passphrase-file "$BACKUP_PASSPHRASE_FILE" --output restore.dump --decrypt backup.dump.gpg`, then validate with `pg_restore --list` before restoring with `pg_restore --clean --if-exists --no-owner --no-acl`. Never test restore against the live production database.
7. Verify evidence objects and their SHA-256 hashes after replication and restore.
8. Confirm bucket versioning and replication state on the remote target. The production overlay no longer starts a second MinIO container on the same host; deployment refuses local/placeholder targets and requires an HTTPS endpoint. Confirm the provider's replication target is in a separate account/region/failure domain and configure provider-side Object Lock/retention where required.
9. Review firewall rules; expose only the intended HTTPS entry point. Do not publish PostgreSQL, Redis, MinIO, Grafana or the gRPC engine directly.

## 6. Operational cautions

- Use an external secrets manager for production secret injection where available.
- Pin and regularly update container image versions after staging validation; do not rely on mutable `latest` tags for a controlled release.
- Set resource limits and database connection capacity to match the deployment scale.
- The production Compose file uses multiple replicas; validate actual load balancing and shared state behavior in the chosen Compose/Swarm/Kubernetes runtime.
- Do not declare production readiness until CI, container builds, integration tests, security checks, backup/restore and a staging acceptance run all pass.

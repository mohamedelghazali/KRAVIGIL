# KRAVIGIL Production Deployment Guide

## 1. Prerequisites
- Linux Server (Ubuntu 22.04 LTS recommended)
- Docker Engine v24+
- Docker Compose v2+
- Minimum 4 CPU cores, 16GB RAM, 100GB SSD

## 2. Security Hardening
Before deployment, ensure the following:
- **TLS Termination**: Place KRAVIGIL behind an NGINX reverse proxy with valid SSL certificates (Let's Encrypt).
- **Database Backups**: Configure a cron job to dump PostgreSQL daily and sync to off-site storage (S3/MinIO).
- **Secrets Management**: Do not use `.env` files in production. Use HashiCorp Vault or AWS Secrets Manager to inject secrets into the containers.
- **Firewall**: Close all ports except 80 and 443.

## 3. Deployment Steps
1. Clone the repository to `/opt/kravigil`.
2. Create a `docker-compose.prod.yml` overriding the default environment variables.
3. Launch the stack:
   ```bash
   docker-compose -f infrastructure/docker-compose.yml -f docker-compose.prod.yml up -d
   ```
4. Run database migrations:
   ```bash
   docker-compose exec backend alembic upgrade head
   ```
5. Create the initial admin user:
   ```bash
   docker-compose exec backend python /app/scripts/seed_db.py
   ```

## 4. Monitoring & Observability
- **Metrics**: Prometheus scrapes `http://backend:8000/metrics`.
- **Logs**: Ship JSON logs from all containers to ELK Stack or Datadog.
- **Tracing**: OpenTelemetry exports traces to Jaeger or Tempo.
- **Alerts**: Set up Grafana alerts for high `kravigil_requests_inprogress` or failed scans.

## 5. Scaling
- **Backend**: Scale horizontally behind NGINX (`docker-compose up -d --scale backend=3`).
- **Workers**: Scale based on CPU usage (`docker-compose up -d --scale worker=10`).
- **Network Engine**: Scale horizontally; the backend will load-balance via gRPC client round-robin.

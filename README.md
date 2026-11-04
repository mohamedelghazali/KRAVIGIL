# KRAVIGIL Core

**Enterprise Vulnerability Assessment & Security Intelligence Platform**

## 🚀 Production Deployment

1. Copy `.env.example` to `.env` and replace every `CHANGE_ME` value with a unique secret. Generate URL-safe passwords with `openssl rand -hex 32`.
2. Set `MINIO_TARGET_URL` to a real external HTTPS S3-compatible endpoint, with separate target credentials and a separate failure domain. The placeholder is deliberately rejected by the deployment script.
3. Configure the application domain in `FRONTEND_URL`, `ALLOWED_ORIGINS`, and `infrastructure/nginx/nginx.prod.conf`.
4. Generate the gRPC CA/server/backend-client/worker-client certificates as described in [Production Deployment](docs/deployment/PRODUCTION.md).
4. Install Docker Engine with the Docker Compose v2 plugin, then run:

```bash
./scripts/go_live.sh
```

The deployment script validates secrets, mTLS certificates, Compose configuration, migrations, remote replication configuration, and the HTTPS health endpoint. It does not create production secrets or certificates automatically. A successful container start is not production certification; follow the staging, retention, backup/restore, load and operations acceptance checklist in the deployment guide.

## 🌟 Features

- Multi-Engine Scans (C++, Nuclei, Semgrep, Trivy, Gitleaks, Prowler)
- **Auth**: JWT + Refresh Tokens, MFA (TOTP), Password Reset, Session Management, Password Changes
- **Scheduled Scans**: Cron-based automated scanning via Celery Beat
- **Evidence Storage**: S3-compatible object storage with SHA-256 evidence integrity; production Object Lock/retention requires provider-side configuration
- **Real-Time Alerts**: Webhooks, Slack, Email, Syslog (CEF for SIEM)
- **AI-Powered Analysis**: Gemini API with prompt injection protection
- **Zero Trust**: PostgreSQL RLS, strict network segmentation, seccomp profiles
- **Recovery**: Off-host S3-compatible evidence/backup replication and encrypted PostgreSQL backups; production provider and restore acceptance are required
- **Threat Intelligence**: AlienVault OTX integration for IOC feeds
- **Observability**: OpenTelemetry, Prometheus, Grafana dashboards included

## 📚 Documentation

- [Architecture](docs/architecture/ARCHITECTURE.md)
- [Security Model](docs/security/SECURITY_MODEL.md)
- [Engine Specification](docs/ENGINE_SPECIFICATION.md)
- [Production Deployment](docs/deployment/PRODUCTION.md)
- [MinIO Replication](docs/operations/MINIO_REPLICATION.md)
- [Operations Guide](docs/OPERATIONS.md)

## 🛠️ Tech Stack

- **Backend**: Python 3.11, FastAPI, SQLAlchemy 2.0, Celery
- **Frontend**: Vue 3, TypeScript, Pinia
- **Network Engine**: C++17, Boost.Asio, gRPC
- **Databases**: PostgreSQL 15, Redis 7, MinIO
- **Observability**: OpenTelemetry, Prometheus, Grafana
- **AI**: Google Gemini API

## 📄 License

Proprietary. All rights reserved. This repository is publicly visible but is **not open source**. No permission to use, copy, modify, or redistribute the code is granted unless the copyright holder provides a separate written license.

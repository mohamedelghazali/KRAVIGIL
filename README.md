# KRAVIGIL Core

**Enterprise Vulnerability Assessment & Security Intelligence Platform**

## 🚀 One-Command Deployment

```bash
cp .env.example .env
./scripts/go_live.sh
```

## 🌟 Features

- Multi-Engine Scans (C++, Nuclei, Semgrep, Trivy, Gitleaks, Prowler)
- **Auth**: JWT + Refresh Tokens, MFA (TOTP), Password Reset, Session Management, Password Changes
- **Scheduled Scans**: Cron-based automated scanning via Celery Beat
- **Evidence Storage**: Immutable storage (MinIO Object Lock) with SHA-256
- **Real-Time Alerts**: Webhooks, Slack, Email, Syslog (CEF for SIEM)
- **AI-Powered Analysis**: Gemini API with prompt injection protection
- **Zero Trust**: PostgreSQL RLS, strict network segmentation, seccomp profiles
- **High Availability**: Cross-cluster MinIO replication and multi-replica deployments
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

Proprietary. All rights reserved.

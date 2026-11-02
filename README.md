# KRAVIGIL Core

**Enterprise Vulnerability Assessment & Security Intelligence Platform**

KRAVIGIL is a distributed, multi-engine platform designed for high-accuracy vulnerability discovery, evidence-based validation, and enterprise-grade security management.

## 🚀 One-Command Deployment

```bash
# 1. Configure environment
cp .env.example .env
# Edit .env with your secrets

# 2. Launch the entire platform
./scripts/go_live.sh
```

Access the dashboard at `http://localhost`.

## 🌟 Features

- **Multi-Engine Scans**: C++ (Network), Nuclei (Web), Semgrep (SAST), Gitleaks (Secrets), Trivy (Containers), Prowler (Cloud).
- **Scheduled Scans**: Cron-based automated scanning via Celery Beat.
- **Evidence Storage**: Immutable storage (MinIO Object Lock) with SHA-256 verification.
- **Real-Time Alerts**: Webhooks, Slack, Email, and Syslog (CEF format for SIEM).
- **AI-Powered Analysis**: Gemini API integration with prompt injection protection.
- **Zero Trust**: PostgreSQL RLS, strict network segmentation, seccomp profiles.
- **High Availability**: Cross-cluster MinIO replication and multi-replica deployments.

## 📚 Documentation

- [Architecture](docs/architecture/ARCHITECTURE.md)
- [Security Model](docs/security/SECURITY_MODEL.md)
- [Engine Specification](docs/ENGINE_SPECIFICATION.md)
- [Production Deployment](docs/deployment/PRODUCTION.md)
- [MinIO Replication](docs/operations/MINIO_REPLICATION.md)
- [Operations Guide](docs/OPERATIONS.md)

## 🛠️ Technology Stack

- **Backend**: Python 3.11, FastAPI, SQLAlchemy 2.0, Celery
- **Frontend**: Vue 3, TypeScript, Pinia, Vite
- **Network Engine**: C++17, Boost.Asio, gRPC, Protocol Buffers
- **Databases**: PostgreSQL 15, Redis 7, MinIO
- **Observability**: OpenTelemetry, Prometheus, Grafana
- **AI**: Google Gemini API

## 📄 License

Proprietary. All rights reserved.

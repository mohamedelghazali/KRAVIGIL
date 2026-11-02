# KRAVIGIL Core

Enterprise Vulnerability Assessment & Security Intelligence Platform.

## Overview

KRAVIGIL is a modular, distributed vulnerability management platform designed for high accuracy, evidence-based validation, and enterprise security.

## Features

- **Network Scanner**: C++ engine using Boost.Asio and gRPC for high-throughput port scanning.
- **Web & Code Scanners**: Integration with Nuclei and Semgrep for comprehensive web and SAST coverage.
- **Container & Secrets Scanning**: Trivy and Gitleaks adapters for modern supply chain security.
- **Evidence-Based Validation**: SHA-256 hashed evidence storage in MinIO with immutable retention.
- **AI Intelligence**: Gemini API integration with prompt injection protection and output validation.
- **Risk Engine**: Dynamic risk scoring using CVSS, EPSS, and CISA KEV data.
- **Multi-Tenancy**: PostgreSQL Row-Level Security (RLS) for strict data isolation.
- **Observability**: OpenTelemetry tracing and Prometheus metrics.

## Architecture

```text
[ Frontend (Vue 3) ] <---> [ Nginx ] <---> [ FastAPI Backend ]
                                                |
                                       [ Celery + Redis ]
                                                |
                         +----------------------+----------------------+
                         |                      |                      |
                 [ C++ Network Engine ]   [ Web Scanners ]     [ AI Gateway ]
                         |                      |                      |
                 [ Target Networks ]     [ Target URLs ]      [ Gemini API ]
                                                |
                                       [ PostgreSQL + MinIO ]
```

## Quick Start

1. Clone the repository:
   ```bash
   git clone https://github.com/your-org/kravigil.git
   cd kravigil
   ```

2. Configure environment:
   ```bash
   cp .env.example .env
   # Edit .env with your secure secrets
   ```

3. Build and run:
   ```bash
   make build
   make up
   ```

4. Access the dashboard at `http://localhost`.
   Default admin credentials will be generated on first boot (check logs).

## Security

- **Scope Guard**: Strict validation to prevent SSRF and unauthorized scanning.
- **Zero Trust**: mTLS and isolated execution planes for all engines.
- **Immutable Evidence**: WORM (Write Once Read Many) storage policies for compliance.
- **API Keys**: Scoped API keys with expiration for machine-to-machine access.

## License

Proprietary. All rights reserved.

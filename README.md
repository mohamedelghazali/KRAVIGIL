# KRAVIGIL

**Enterprise Offensive Security & Vulnerability Intelligence Platform**

KRAVIGIL is a modular platform scaffold for authorized security assessment, asset
visibility, vulnerability evidence management, finding correlation, risk analysis,
and security reporting.

> **Project status:** architecture and repository scaffold. Scanner execution,
> vulnerability validation, agent enrollment, AI providers, and production
> security controls are not yet implemented. Do not treat the current scaffold
> as a production-ready penetration-testing platform.

## Architecture at a glance

- **Backend:** FastAPI, Pydantic 2, SQLAlchemy 2, PostgreSQL.
- **Workers:** Celery with Redis for asynchronous jobs.
- **Engines:** isolated network and web scanning components, with extension
  points for API, SAST, DAST, cloud, container, dependency, and secret analysis.
- **AI:** provider gateway designed for local-first analysis and optional Gemini
  reasoning subject to data policy and human oversight.
- **Frontend:** Vue 3, TypeScript, Pinia, and Vue Router.
- **Evidence:** metadata in PostgreSQL and a planned object-storage integration.
- **Security:** explicit target authorization, tenant isolation, auditability,
  bounded execution, and evidence validation are design requirements.

## Repository layout

- `backend/` — API, domain services, persistence, and integrations.
- `workers/` — orchestration and asynchronous processing.
- `engines/` — scanning engine implementations and extension points.
- `ai/` — AI gateway, providers, intelligence modules, and evaluation.
- `agents/` — future remote-agent lifecycle and identity.
- `shared/` — versioned contracts, enums, and protocol definitions.
- `infrastructure/` — deployment, network, isolation, storage, and monitoring.
- `frontend/` — Vue application.
- `tests/` — unit, integration, security, performance, and regression tests.
- `docs/` — architecture, security, engine, operations, and testing documents.

## Local development

Requirements: Python 3.12+, Node.js 20+, and npm.

### Backend

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
uvicorn backend.main:app --reload
```

The API health endpoint is `GET /health`. Database and Redis services must be
configured before enabling features that depend on them.

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

Set `VITE_API_BASE_URL` to the backend API base URL when a proxy is not used.

### Tests and lint

```powershell
pytest -q
ruff check backend workers engines ai agents shared tests
```

## Security boundaries

- Only assess targets for which the operator has explicit authorization.
- Detection is not confirmation; findings require evidence and independent
  validation before being marked confirmed.
- AI output is advisory and must not grant authorization, execute arbitrary
  commands, or independently confirm vulnerabilities.
- Never commit API keys, database credentials, certificates, or real customer
  evidence. Use environment secrets or a dedicated secret manager.
- Scanner workers must run with least privilege, restricted egress, and resource
  limits before any active scanning capability is enabled.

## License

No open-source license has been selected yet. Unless a separate license is
added, all rights remain reserved by the copyright holder.

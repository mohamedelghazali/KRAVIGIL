# KRAVIGIL Architecture

## 1. Planes

- **Control Plane**: API, Auth, Scheduling, Database (PostgreSQL).
- **Execution Plane**: Scanners (C++, Python), isolated in network namespaces.
- **Data Plane**: Evidence (MinIO), Cache (Redis), Logs.
- **Intelligence Plane**: Correlation, Risk Engine, AI Gateway.

## 2. Data Flow

1. User creates Target & Scan via API.
2. Celery Worker picks up Scan task.
3. Worker communicates with Engine (via gRPC) inside Execution Plane.
4. Engine streams findings back to Worker.
5. Worker normalizes, correlates, and scores findings.
6. Findings and Evidence are stored in Data Plane.
7. Webhooks and WebSocket events notify the user.

## 3. Security Boundaries

- **Scope Guard**: Verifies target IPs against allowlists and blocks internal metadata endpoints.
- **Sandboxing**: Engines run as non-root, read-only filesystem, with dropped capabilities (except `NET_RAW` for network scanning).
- **RLS**: PostgreSQL enforces tenant isolation at the DB layer.
- **AI Security**: Untrusted evidence is sanitized to prevent Prompt Injection before being sent to Gemini.

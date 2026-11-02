# KRAVIGIL Security Model

## 1. Authentication & Authorization
- **JWT**: Short-lived access tokens (default 30 minutes) with strict audience (`kravigil-api`) and issuer (`kravigil-core`) validation.
- **API Keys**: Scoped to tenants, hashed using SHA-256, and can be revoked instantly.
- **RBAC**: Roles (`admin`, `analyst`, `viewer`) enforced at the dependency level using FastAPI `require_role`.

## 2. Tenant Isolation
- Enforced at the database layer using PostgreSQL Row-Level Security (RLS).
- Every query executed by a Celery worker or API request must set `app.tenant_id` locally within the transaction.
- Unique constraints and foreign keys include `tenant_id` to prevent cross-tenant relation poisoning.

## 3. Scope Guard
- An independent module (`backend.security.scope_guard`) that validates every target before scanning.
- **DNS Rebinding Protection**: Resolves the hostname and checks the resulting IP against blocklists (RFC 1918, Loopback, Cloud Metadata `169.254.169.254`).
- **Redirect Validation**: Validates every HTTP 3xx redirect destination against the same blocklists.

## 4. Sandboxing & Execution Plane
- **Network Engine**: Runs as non-root, drops all capabilities except `NET_RAW`, mounts a read-only root filesystem, and uses `seccomp` profiles.
- **Workers**: Isolated in the `execution_plane` network, with no direct access to the `data_plane` (PostgreSQL/MinIO).
- **Egress Proxy**: All outbound traffic from workers goes through an Egress Gateway that enforces the Scope Guard.

## 5. AI Security
- **Untrusted Evidence**: All evidence is treated as untrusted input.
- **Sanitization**: HTML/JS tags are stripped, and potential prompt injection patterns are redacted before reaching the LLM.
- **Output Validation**: The AI's response is strictly validated against a JSON schema. It cannot directly mutate findings or state without a deterministic policy check.

## 6. Evidence Integrity
- **Immutable Storage**: Evidence is stored in MinIO with Object Lock (COMPLIANCE mode) and Versioning.
- **Hash Verification**: SHA-256 hash is calculated upon ingestion and verified upon retrieval.
- **Separate Permissions**: The Evidence Writer cannot delete or modify objects; only the Retention Administrator can change policies.

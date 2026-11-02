\# KRAVIGIL Operations Guide

## 1. Daily Operations

- **Health Checks**: Monitor \`/api/v1/system/health\` via UptimeRobot or Prometheus Alertmanager. Expect \`status: ok\`.
- **Log Aggregation**: Ship logs to ELK or Datadog. Filter for \`level: ERROR\` and \`level: CRITICAL\`.
- **Database Backups**: 
  - PostgreSQL: Run \`pg_dump -U kravigil_admin -Fc kravigil_db > backup.dump\` daily.
  - Store backups in an off-site S3 bucket with Object Lock (COMPLIANCE).
- **MinIO Retention**: Verify Object Lock policies are active:
  \`\`\`bash
  mc retention info --recursive evmx/evidence-immutable
  \`\`\`

## 2. Scaling & Performance

- **Workers**: If Redis queue (\`celery\`) length exceeds 1000 for more than 5 minutes, scale workers:
  \`\`\`bash
  docker-compose up -d --scale worker=10
  \`\`\`
- **Backend API**: If p99 latency exceeds 500ms, scale backend replicas behind NGINX.
- **Network Engine**: C++ engine is CPU-bound. Ensure the host has at least 4 cores dedicated to the engine.

## 3. Incident Response

- **Compromised Scanner**: If a worker is suspected to be compromised (e.g., via a malicious payload from a target), immediately:
  1. Isolate the worker node.
  2. Destroy the container (\`docker rm -f <worker-id>\`).
  3. Check Scope Guard logs for SSRF attempts.
  4. Review AI Gateway logs for Prompt Injection attempts.
- **Data Breach**: 
  1. Revoke all API keys immediately.
  2. Rotate \`SECRET_KEY\` (invalidates all JWTs).
  3. Restore PostgreSQL from the last clean backup.
  4. Review \`audit_logs\` for unauthorized access.

## 4. Updates & Maintenance

- **Applying Updates**:
  \`\`\`bash
  git pull origin main
  make build
  make down
  make up
  docker-compose exec backend alembic upgrade head
  \`\`\`
- **Rotating Secrets**: Use HashiCorp Vault or AWS Secrets Manager to inject new secrets into \`.env\` without downtime.

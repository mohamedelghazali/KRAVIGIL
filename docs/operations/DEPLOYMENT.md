# KRAVIGIL Deployment Operations

This page is the operational entry point for deployment. It does not replace environment-specific acceptance evidence.

## Deployment paths

- **Production prerequisites and deployment:** [Production Deployment Guide](../deployment/PRODUCTION.md)
- **Staging acceptance procedure:** [Staging Acceptance Runbook](STAGING_ACCEPTANCE.md)
- **Off-host restore evidence:** [Restore Drill Evidence Template](RESTORE_DRILL_EVIDENCE_TEMPLATE.md)

## Production deployment command

From the repository root, after completing every prerequisite in the production guide and reviewing the target environment:

```bash
bash scripts/deploy_prod.sh
```

The script is a guarded deployment procedure. It requires a configured `.env`, HTTPS domain and certificate, network-engine mTLS identities, and a distinct off-host HTTPS S3-compatible replication target. It builds and starts services, applies migrations, provisions the restricted application DB role, and checks the API health endpoint.

Do not run it against an unapproved environment or treat a successful script exit as proof of production acceptance. Complete the post-deployment checks in the production guide and retain evidence.

## Staging requirements

Staging must be isolated from production and use synthetic data, separate credentials, and authorized scanner targets only. Follow the staging runbook and record PASS / INCOMPLETE / FAIL for each acceptance item. Do not mark staging, restore, or performance gates complete without actual runtime evidence.

## Safety boundaries

- Never commit `.env`, private keys, certificates, API tokens, backup passphrases, or customer data.
- Do not expose PostgreSQL, Redis, MinIO, Grafana, or the internal gRPC network engine directly to the public internet.
- Do not run scans outside explicitly authorized scope.
- Keep the release decision NO-GO until every applicable release gate has evidence.

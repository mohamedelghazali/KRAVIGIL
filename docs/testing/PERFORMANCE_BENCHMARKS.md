# KRAVIGIL Performance and Capacity Baseline

Status: harness implemented; representative capacity acceptance remains open.

## Purpose and limits

The repository includes Prometheus instrumentation and Grafana dashboards, but monitoring configuration is not evidence of capacity. This runbook defines a repeatable, bounded, read-only API baseline. It does not certify production capacity, database/object-storage throughput, worker queue capacity, or scan throughput.

Do not run load tests against third-party systems or targets without written authorization. Use an isolated staging deployment with synthetic tenant data. Do not use production customer data.

## Runner

The runner is `scripts/performance/run_api_load.py`. It uses the already-pinned `httpx` dependency and writes a JSON report. It is deliberately limited to these GET endpoints:

- `/health` — application liveness only; it does not measure database or Redis health.
- `/api/v1/system/version` — lightweight API request path.
- `/api/v1/targets/` — authenticated, tenant-scoped database read; requires `KRAVIGIL_BEARER_TOKEN`.

Mutating endpoints, scan dispatch, evidence uploads, arbitrary paths, and remote plain HTTP are rejected. The default request rate is 5 requests/second and the hard cap is 15 requests/second to remain below the application's configured 1,000 requests/minute rate limit for a single token/IP. The runner does not automatically retry failed requests.

## Example

Run from the repository root against a dedicated staging environment:

```powershell
$env:KRAVIGIL_BEARER_TOKEN = "<short-lived-staging-token>"
python scripts/performance/run_api_load.py --base-url https://staging.example.com --path /api/v1/targets/ --duration-seconds 120 --concurrency 5 --requests-per-second 5 --output artifacts/performance/targets-baseline.json
Remove-Item Env:KRAVIGIL_BEARER_TOKEN
```

For a local development instance, `http://127.0.0.1:8000` is accepted. Never put tokens on the command line or commit them to the repository. Use a dedicated least-privilege staging account and revoke its token after testing.

## Reported measurements

Each run records elapsed duration, completed/successful/failed request counts, HTTP status distribution, error rate, achieved throughput, p50/p95/p99/max client-observed latency, configured concurrency/rate, and threshold outcome. Preserve the raw JSON report with the tested application SHA, deployment configuration, host/container resource limits, database/Redis/object-storage versions, and monitoring snapshots.

Client-observed latency includes network and proxy overhead. Compare equivalent runs from the same load-generator location. Do not combine results from unlike hardware or staging topologies.

## Initial smoke thresholds (provisional)

The runner's defaults (p95 <= 1,000 ms and error rate <= 1%) are engineering smoke thresholds only. They are not approved product SLOs and do not constitute release acceptance. A service owner must approve workload shape and SLOs before the results can be used as a capacity gate.

## Required capacity acceptance plan

1. Record the exact candidate SHA and deployment topology, including API replicas, worker replicas, CPU/memory limits, database pool settings, Redis, MinIO/S3, network latency, and load-generator capacity.
2. Define realistic tenant/user mix and read/write proportions using synthetic data. Include target listing, finding listing, report listing, authentication, and controlled scan enqueue only in an isolated authorized test plan.
3. Establish warm-up, steady-state, ramp, and soak phases. Keep scan execution tests separate from API read tests so that scanner activity cannot escape authorized scope.
4. Measure API p50/p95/p99, throughput, 4xx/5xx/429 rates, CPU, memory, DB pool wait/active connections, query latency, Redis latency/queue depth, object-storage latency, Celery queue age, worker utilization, and scan completion time.
5. Run at multiple load levels and identify the saturation knee. Repeat each representative profile at least three times and retain raw reports.
6. Exercise recovery behavior: worker restart, Redis reconnect, database failover/reconnect, and object-storage throttling in a controlled staging environment.
7. Compare results with owner-approved SLOs and document bottlenecks, remediation, retest SHA, and final decision.

## Acceptance status

KV-009 remains OPEN until the workload profile and SLOs are approved, representative tests run on a production-like staging topology, resource/queue/storage measurements are captured, and the evidence is reviewed. No live staging load test has been claimed by adding this harness.

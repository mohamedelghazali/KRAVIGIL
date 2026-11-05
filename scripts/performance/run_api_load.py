from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

ALLOWED_PATHS = {"/health", "/api/v1/system/version", "/api/v1/targets/"}
MAX_DURATION_SECONDS = 3600
MAX_CONCURRENCY = 100
MAX_REQUESTS_PER_SECOND = 15.0
DEFAULT_TIMEOUT_SECONDS = 15.0


def percentile(values: list[float], percentile_value: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, math.ceil((percentile_value / 100) * len(ordered)) - 1)
    return round(ordered[index], 3)


def validate_target(base_url: str, path: str, token: str | None) -> str:
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("base URL must be an absolute HTTP(S) URL")
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise ValueError("base URL must not contain a path, query, or fragment")
    if parsed.scheme != "https" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("HTTP is permitted only for localhost; use HTTPS for remote targets")
    if path not in ALLOWED_PATHS:
        raise ValueError(f"path is not in the read-only allowlist: {path}")
    if path == "/api/v1/targets/" and not token:
        raise ValueError("KRAVIGIL_BEARER_TOKEN is required for the tenant-scoped targets endpoint")
    return base_url.rstrip("/") + path


async def run_load(
    url: str,
    token: str | None,
    duration_seconds: int,
    concurrency: int,
    requests_per_second: float,
    timeout_seconds: float,
) -> dict[str, Any]:
    started_at = datetime.now(timezone.utc).isoformat()
    loop = asyncio.get_running_loop()
    started = loop.time()
    deadline = started + duration_seconds
    next_slot = started
    schedule_lock = asyncio.Lock()
    latencies: list[float] = []
    statuses: Counter[str] = Counter()
    failures: Counter[str] = Counter()
    completed = 0
    headers = {"Authorization": f"Bearer {token}"} if token else {}

    limits = httpx.Limits(
        max_connections=concurrency,
        max_keepalive_connections=concurrency,
    )
    timeout = httpx.Timeout(timeout_seconds)
    async with httpx.AsyncClient(limits=limits, timeout=timeout, follow_redirects=False) as client:
        async def worker() -> None:
            nonlocal next_slot, completed
            while loop.time() < deadline:
                async with schedule_lock:
                    slot = max(loop.time(), next_slot)
                    next_slot = slot + (1.0 / requests_per_second)
                delay = slot - loop.time()
                if delay > 0:
                    await asyncio.sleep(delay)
                if loop.time() >= deadline:
                    return
                request_started = loop.time()
                try:
                    response = await client.get(url, headers=headers)
                    latency_ms = (loop.time() - request_started) * 1000
                    latencies.append(latency_ms)
                    statuses[str(response.status_code)] += 1
                    if not 200 <= response.status_code < 300:
                        failures[f"http_{response.status_code}"] += 1
                except httpx.TimeoutException:
                    failures["timeout"] += 1
                except httpx.HTTPError as exc:
                    failures[type(exc).__name__] += 1
                finally:
                    completed += 1

        await asyncio.gather(*(worker() for _ in range(concurrency)))

    elapsed = loop.time() - started
    failed = sum(failures.values())
    successful = completed - failed
    return {
        "started_at": started_at,
        "target_path": urlparse(url).path,
        "duration_seconds": round(elapsed, 3),
        "configured_concurrency": concurrency,
        "configured_requests_per_second": requests_per_second,
        "requests_completed": completed,
        "successful_requests": successful,
        "failed_requests": failed,
        "error_rate_percent": round((failed / completed) * 100, 3) if completed else 0.0,
        "throughput_requests_per_second": round(completed / elapsed, 3) if elapsed else 0.0,
        "latency_ms": {
            "p50": percentile(latencies, 50),
            "p95": percentile(latencies, 95),
            "p99": percentile(latencies, 99),
            "max": round(max(latencies), 3) if latencies else None,
        },
        "http_status_counts": dict(statuses),
        "failure_counts": dict(failures),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a bounded, read-only KRAVIGIL API performance baseline."
    )
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--path", choices=sorted(ALLOWED_PATHS), default="/api/v1/system/version")
    parser.add_argument("--duration-seconds", type=int, default=120)
    parser.add_argument("--concurrency", type=int, default=5)
    parser.add_argument("--requests-per-second", type=float, default=5.0)
    parser.add_argument("--timeout-seconds", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--max-error-rate-percent", type=float, default=1.0)
    parser.add_argument("--max-p95-ms", type=float, default=1000.0)
    return parser.parse_args()


async def async_main(args: argparse.Namespace) -> int:
    if not 1 <= args.duration_seconds <= MAX_DURATION_SECONDS:
        raise ValueError(f"duration must be between 1 and {MAX_DURATION_SECONDS} seconds")
    if not 1 <= args.concurrency <= MAX_CONCURRENCY:
        raise ValueError(f"concurrency must be between 1 and {MAX_CONCURRENCY}")
    if not 0 < args.requests_per_second <= MAX_REQUESTS_PER_SECOND:
        raise ValueError(f"request rate must be greater than 0 and at most {MAX_REQUESTS_PER_SECOND}")
    if not 0.1 <= args.timeout_seconds <= 120:
        raise ValueError("timeout must be between 0.1 and 120 seconds")
    if not 0 <= args.max_error_rate_percent <= 100 or args.max_p95_ms <= 0:
        raise ValueError("acceptance thresholds are invalid")

    token = os.getenv("KRAVIGIL_BEARER_TOKEN")
    url = validate_target(args.base_url, args.path, token)
    result = await run_load(
        url=url,
        token=token,
        duration_seconds=args.duration_seconds,
        concurrency=args.concurrency,
        requests_per_second=args.requests_per_second,
        timeout_seconds=args.timeout_seconds,
    )
    result["provisional_thresholds"] = {
        "max_error_rate_percent": args.max_error_rate_percent,
        "max_p95_ms": args.max_p95_ms,
    }
    p95 = result["latency_ms"]["p95"]
    result["thresholds_passed"] = (
        result["error_rate_percent"] <= args.max_error_rate_percent
        and p95 is not None
        and p95 <= args.max_p95_ms
    )
    rendered = json.dumps(result, indent=2, sort_keys=True)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    return 0 if result["thresholds_passed"] else 2


def main() -> int:
    try:
        return asyncio.run(async_main(parse_args()))
    except (ValueError, OSError) as exc:
        print(f"performance runner error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

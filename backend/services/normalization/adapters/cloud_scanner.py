import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List

from backend.services.normalization.adapters.base import BaseEngineAdapter

logger = logging.getLogger(__name__)


class CloudScannerAdapter(BaseEngineAdapter):
    """Run Prowler and normalize its OCSF JSON findings."""

    def __init__(self):
        super().__init__(binary_path="prowler", timeout_seconds=3600)

    def scan(self, provider: str = "aws") -> List[Dict[str, Any]]:
        provider = provider.lower()
        if provider not in {"aws", "azure", "gcp"}:
            raise ValueError(f"Unsupported cloud provider: {provider}")

        with tempfile.TemporaryDirectory(prefix="kravigil-prowler-") as output_dir:
            args = [provider, "-M", "json-ocsf", "-o", output_dir, "-F", "kravigil"]
            if provider == "azure":
                args.append("--sp-env-auth")
            elif provider == "gcp":
                credentials_file = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
                if credentials_file:
                    args.extend(["--credentials-file", credentials_file])

            self.execute(args)
            report_files = sorted(Path(output_dir).glob("*.json"))
            if not report_files:
                raise RuntimeError("Prowler completed without producing a JSON-OCSF report")

            results: List[Dict[str, Any]] = []
            for report_file in report_files:
                results.extend(self.parse_output(report_file.read_text(encoding="utf-8")))
            return results

    def parse_output(self, raw_output: str) -> List[Dict[str, Any]]:
        if not raw_output.strip():
            return []

        try:
            payload = json.loads(raw_output)
            records = payload if isinstance(payload, list) else [payload]
        except json.JSONDecodeError:
            records = []
            for line in raw_output.splitlines():
                if not line.strip():
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    logger.warning("Skipping malformed Prowler JSON output line")
        
        results: List[Dict[str, Any]] = []
        for record in records:
            if not isinstance(record, dict) or str(record.get("status_code", "")).upper() != "FAIL":
                continue

            finding = record.get("finding_info") or {}
            resources = record.get("resources") or []
            resource = resources[0] if resources and isinstance(resources[0], dict) else {}
            results.append({
                "title": finding.get("title") or record.get("message") or "Cloud misconfiguration",
                "severity": str(record.get("severity") or "MEDIUM").upper(),
                "description": finding.get("desc") or record.get("status_detail") or record.get("message") or "",
                "check_id": (record.get("metadata") or {}).get("event_code"),
                "resource_arn": resource.get("uid") or resource.get("name"),
                "cwe_id": None,
                "cve_id": None,
                "raw": record,
            })
        return results

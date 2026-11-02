import json
import logging
from typing import List, Dict, Any
from backend.services.normalization.adapters.base import BaseEngineAdapter

logger = logging.getLogger(__name__)

class CloudScannerAdapter(BaseEngineAdapter):
    def __init__(self):
        super().__init__(binary_path="prowler", timeout_seconds=1800)

    def scan(self, provider: str = "aws") -> List[Dict[str, Any]]:
        args = [
            provider,
            "-M", "json",
            "-F", "/dev/stdout",
            "--quiet"
        ]
        raw_output = self.execute(args)
        return self.parse_output(raw_output)

    def parse_output(self, raw_output: str) -> List[Dict[str, Any]]:
        results = []
        if not raw_output.strip():
            return results

        try:
            lines = raw_output.strip().splitlines()
            for line in lines:
                data = json.loads(line)
                status = data.get("status", "").upper()
                if status in ["FAIL", "FAILED"]:
                    results.append({
                        "title": data.get("check_title", "Cloud Misconfiguration"),
                        "severity": data.get("severity", "MEDIUM").upper(),
                        "description": data.get("description", ""),
                        "cwe_id": None,
                        "cve_id": None,
                        "raw": data
                    })
        except json.JSONDecodeError:
            logger.error("Failed to parse Cloud Scanner JSON output")
        return results

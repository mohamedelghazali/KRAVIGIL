import json
import logging
from typing import List, Dict, Any
from backend.services.normalization.adapters.base import BaseEngineAdapter

logger = logging.getLogger(__name__)

class TrivyAdapter(BaseEngineAdapter):
    def __init__(self):
        super().__init__(binary_path="trivy", timeout_seconds=900)

    def scan(self, image_name: str) -> List[Dict[str, Any]]:
        args = ["image", "--format", "json", "--quiet", image_name]
        raw_output = self.execute(args)
        return self.parse_output(raw_output)

    def parse_output(self, raw_output: str) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        if not raw_output.strip():
            return results
        try:
            data = json.loads(raw_output)
            for result in data.get("Results", []):
                for vuln in result.get("Vulnerabilities", []):
                    results.append({
                        "title": vuln.get("Title") or vuln.get("VulnerabilityID"),
                        "severity": vuln.get("Severity", "UNKNOWN").upper(),
                        "description": vuln.get("Description", ""),
                        "cve_id": vuln.get("VulnerabilityID"),
                        "package_name": vuln.get("PkgName"),
                        "installed_version": vuln.get("InstalledVersion"),
                        "fixed_version": vuln.get("FixedVersion"),
                        "raw": vuln
                    })
        except json.JSONDecodeError:
            logger.error("Failed to parse Trivy JSON output")
        return results

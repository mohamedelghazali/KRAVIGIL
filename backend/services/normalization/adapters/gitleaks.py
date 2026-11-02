import json
import logging
from typing import List, Dict, Any
from backend.services.normalization.adapters.base import BaseEngineAdapter

logger = logging.getLogger(__name__)

class GitleaksAdapter(BaseEngineAdapter):
    def __init__(self):
        super().__init__(binary_path="gitleaks", timeout_seconds=600)

    def scan(self, repo_path: str) -> List[Dict[str, Any]]:
        args = [
            "detect", "--source", repo_path, "--report-format", "json",
            "--report-path", "/dev/stdout", "--no-git", "-v"
        ]
        raw_output = self.execute(args)
        return self.parse_output(raw_output)

    def parse_output(self, raw_output: str) -> List[Dict[str, Any]]:
        results = []
        if not raw_output.strip():
            return results
        try:
            data = json.loads(raw_output)
            for finding in data:
                results.append({
                    "title": finding.get("Description", "Exposed Secret"),
                    "severity": "HIGH",
                    "description": f"Secret detected in {finding.get('File')} at line {finding.get('StartLine')}",
                    "file": finding.get("File"),
                    "line": finding.get("StartLine"),
                    "rule_id": finding.get("RuleID"),
                    "raw": finding
                })
        except json.JSONDecodeError:
            logger.error("Failed to parse Gitleaks JSON output")
        return results

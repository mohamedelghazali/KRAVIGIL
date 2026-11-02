import json
import logging
from typing import List, Dict, Any
from backend.services.normalization.adapters.base import BaseEngineAdapter

logger = logging.getLogger(__name__)

class SemgrepAdapter(BaseEngineAdapter):
    def __init__(self):
        super().__init__(binary_path="semgrep", timeout_seconds=1200)

    def scan(self, code_path: str, config: str = "auto") -> List[Dict[str, Any]]:
        args = [
            "--config", config,
            "--json",
            "--quiet",
            code_path
        ]
        raw_output = self.execute(args)
        return self.parse_output(raw_output)

    def parse_output(self, raw_output: str) -> List[Dict[str, Any]]:
        results = []
        try:
            data = json.loads(raw_output)
            for finding in data.get("results", []):
                extra = finding.get("extra", {})
                metadata = extra.get("metadata", {})
                
                results.append({
                    "check_id": finding.get("check_id"),
                    "path": finding.get("path"),
                    "line": finding.get("start", {}).get("line"),
                    "message": extra.get("message"),
                    "severity": extra.get("severity", "WARNING").upper(),
                    "cwe_id": metadata.get("cwe", [None])[0] if metadata.get("cwe") else None,
                    "owasp": metadata.get("owasp", [None])[0] if metadata.get("owasp") else None,
                    "raw": finding
                })
        except json.JSONDecodeError:
            logger.error("Failed to parse Semgrep JSON output")
        return results

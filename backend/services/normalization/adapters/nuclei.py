import json
import logging
from typing import List, Dict, Any
from backend.services.normalization.adapters.base import BaseEngineAdapter

logger = logging.getLogger(__name__)

class NucleiAdapter(BaseEngineAdapter):
    def __init__(self):
        super().__init__(binary_path="nuclei", timeout_seconds=1800)

    def scan(self, target_url: str, templates: str = "cves,vulnerabilities") -> List[Dict[str, Any]]:
        args = [
            "-u", target_url,
            "-json",
            "-silent",
            "-t", templates,
            "-rl", "150",
            "-c", "25"
        ]
        raw_output = self.execute(args)
        return self.parse_output(raw_output)

    def parse_output(self, raw_output: str) -> List[Dict[str, Any]]:
        results = []
        for line in raw_output.strip().splitlines():
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                info = data.get("info", {})
                classification = info.get("classification", {})
                
                results.append({
                    "template_id": data.get("template-id"),
                    "name": info.get("name"),
                    "severity": info.get("severity", "unknown").upper(),
                    "description": info.get("description", ""),
                    "matched_at": data.get("matched-at"),
                    "host": data.get("host"),
                    "cve_id": classification.get("cve-id", [None])[0] if classification.get("cve-id") else None,
                    "cwe_id": classification.get("cwe-id", [None])[0] if classification.get("cwe-id") else None,
                    "raw": data
                })
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse Nuclei JSON line: {line[:100]}")
        return results

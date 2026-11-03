import ipaddress
import json
import logging
from typing import List, Dict, Any, Optional
from urllib.parse import urlsplit, urlunsplit

from backend.services.normalization.adapters.base import BaseEngineAdapter

logger = logging.getLogger(__name__)


class NucleiAdapter(BaseEngineAdapter):
    def __init__(self):
        super().__init__(binary_path="nuclei", timeout_seconds=1800)

    def scan(
        self,
        target_url: str,
        templates: str = "cves,vulnerabilities",
        pinned_ip: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        args = [
            "-u", target_url,
            "-json",
            "-silent",
            "-tags", templates,
            "-disable-redirects",
            "-rl", "150",
            "-c", "25",
        ]

        if pinned_ip:
            parsed = urlsplit(target_url)
            hostname = parsed.hostname
            if not hostname or parsed.scheme.lower() not in {"http", "https"}:
                raise ValueError("A valid HTTP(S) URL is required for pinned scanning")
            ip_address = ipaddress.ip_address(pinned_ip)
            pinned_host = f"[{ip_address.compressed}]" if ip_address.version == 6 else ip_address.compressed
            netloc = pinned_host
            if parsed.port:
                netloc = f"{netloc}:{parsed.port}"
            pinned_url = urlunsplit((parsed.scheme, netloc, parsed.path or "/", parsed.query, ""))
            host_header = hostname
            if parsed.port:
                host_header = f"{hostname}:{parsed.port}"
            args[1] = pinned_url
            args.extend(["-H", f"Host: {host_header}"])
            if parsed.scheme.lower() == "https" and not _is_ip(hostname):
                args.extend(["-sni", hostname])

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
                    "raw": data,
                })
            except json.JSONDecodeError:
                logger.warning("Failed to parse Nuclei JSON output line")
        return results


def _is_ip(hostname: str) -> bool:
    try:
        ipaddress.ip_address(hostname)
        return True
    except ValueError:
        return False

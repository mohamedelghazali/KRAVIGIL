import logging
from typing import Dict, List

logger = logging.getLogger(__name__)

class ComplianceMapper:
    CWE_TO_OWASP = {
        "CWE-89": "A03:2021 - Injection",
        "CWE-79": "A03:2021 - Injection",
        "CWE-22": "A01:2021 - Broken Access Control",
        "CWE-284": "A01:2021 - Broken Access Control",
        "CWE-502": "A08:2021 - Software and Data Integrity Failures",
        "CWE-798": "A07:2021 - Identification and Authentication Failures",
    }

    @staticmethod
    def map_to_owasp(cwe_id: str) -> str:
        if not cwe_id:
            return "Unmapped"
        return ComplianceMapper.CWE_TO_OWASP.get(cwe_id, "Other")

    @staticmethod
    def calculate_compliance_score(findings: List[Dict]) -> Dict[str, int]:
        score = {
            "A01:2021 - Broken Access Control": 0,
            "A02:2021 - Cryptographic Failures": 0,
            "A03:2021 - Injection": 0,
            "A04:2021 - Insecure Design": 0,
            "A05:2021 - Security Misconfiguration": 0,
            "A06:2021 - Vulnerable and Outdated Components": 0,
            "A07:2021 - Identification and Authentication Failures": 0,
            "A08:2021 - Software and Data Integrity Failures": 0,
            "A09:2021 - Security Logging and Monitoring Failures": 0,
            "A10:2021 - Server-Side Request Forgery (SSRF)": 0,
            "Unmapped": 0
        }

        for finding in findings:
            cwe = finding.get("cwe_id")
            category = ComplianceMapper.map_to_owasp(cwe)
            if category in score:
                score[category] += 1
            else:
                score["Unmapped"] += 1

        return score

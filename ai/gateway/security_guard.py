import re
from typing import Dict, Any

class SecurityGuard:
    def __init__(self):
        self.injection_patterns = [
            r"(?i)ignore\s+(all\s+)?previous\s+instructions",
            r"(?i)system\s+prompt",
            r"(?i)you\s+are\s+now",
            r"(?i)reveal\s+your",
            r"(?i)disregard\s+(all\s+)?prior"
        ]

    def sanitize_evidence(self, raw_text: str, max_length: int = 5000) -> str:
        clean_text = re.sub(r'<[^>]+>', ' ', raw_text)
        
        for pattern in self.injection_patterns:
            clean_text = re.sub(pattern, "[REDACTED_INJECTION_ATTEMPT]", clean_text)
            
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()
        return clean_text[:max_length]

    def classify_data(self, data: Dict[str, Any]) -> str:
        sensitive_keys = ["password", "token", "secret", "api_key", "authorization"]
        data_str = str(data).lower()
        
        for key in sensitive_keys:
            if key in data_str:
                return "SENSITIVE"
        return "PUBLIC"

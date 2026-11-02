import logging
import re
from typing import Any, Dict

logger = logging.getLogger(__name__)


class SecurityGuard:
    def __init__(self):
        self.injection_patterns = [
            r"(?i)ignore\s+(all\s+)?previous\s+instructions",
            r"(?i)system\s+prompt",
            r"(?i)you\s+are\s+now",
            r"(?i)reveal\s+your",
            r"(?i)disregard\s+(all\s+)?prior",
            r"(?i)forget\s+(all\s+)?previous",
        ]
        self.secret_patterns = [
            r"(?i)authorization\s*:\s*bearer\s+[a-z0-9\-._~+/]+=*",
            r"(?i)bearer\s+[a-z0-9\-._~+/]+=*",
            r"AKIA[0-9A-Z]{16}",
            r"eyJ[A-Za-z0-9_-]+=*\.[A-Za-z0-9_-]+=*\.?[A-Za-z0-9_./+-]*",
            r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----.*?-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
        ]
        self.sensitive_keys = {
            "password", "passwd", "token", "secret", "api_key", "apikey",
            "authorization", "private_key", "access_key", "refresh_token",
        }

    def sanitize_evidence(self, raw_text: str, max_length: int = 15000) -> str:
        if not isinstance(raw_text, str) or max_length <= 0:
            return ""
        clean_text = re.sub(r"<script\b[^>]*>.*?</script\s*>", " ", raw_text, flags=re.DOTALL | re.IGNORECASE)
        clean_text = re.sub(r"<style\b[^>]*>.*?</style\s*>", " ", clean_text, flags=re.DOTALL | re.IGNORECASE)
        clean_text = re.sub(r"<[^>]+>", " ", clean_text)
        for pattern in self.injection_patterns:
            clean_text = re.sub(pattern, "[REDACTED_PROMPT_INJECTION]", clean_text)
        for pattern in self.secret_patterns:
            clean_text = re.sub(pattern, "[REDACTED_SECRET]", clean_text, flags=re.DOTALL)
        return re.sub(r"\s+", " ", clean_text).strip()[:max_length]

    def validate_data_policy(self, finding_data: Dict[str, Any]) -> bool:
        if not isinstance(finding_data, dict):
            return False

        def contains_sensitive_key(value: Any) -> bool:
            if isinstance(value, dict):
                for key, nested in value.items():
                    normalized = str(key).strip().lower().replace("-", "_")
                    if normalized in self.sensitive_keys or contains_sensitive_key(nested):
                        return True
            elif isinstance(value, (list, tuple)):
                return any(contains_sensitive_key(item) for item in value)
            return False

        if contains_sensitive_key(finding_data):
            logger.warning("Data policy violation: sensitive field detected")
            return False
        return True

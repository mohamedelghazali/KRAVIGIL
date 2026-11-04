import html
import logging
import re
from typing import Any, Dict

logger = logging.getLogger(__name__)


class SecurityGuard:
    """Bounded sanitization and data-policy checks for untrusted AI evidence."""

    MAX_INPUT_LENGTH = 65536
    MAX_OUTPUT_LENGTH = 15000

    def __init__(self):
        self.injection_patterns = [
            r"(?i)ignore\s+(?:all\\s+)?(?:the\\s+)?(?:previous|prior|above|earlier)\s+(?:instructions|rules|messages)",
            r"(?i)system\s+prompt",
            r"(?i)you\s+are\s+now",
            r"(?i)reveal\s+(?:your|the)\s+(?:system\s+)?prompt",
            r"(?i)disregard\s+(?:all\s+)?(?:prior|previous|above)\s+(?:instructions|rules|messages)?",
            r"(?i)forget\s+(?:all\s+)?previous\s+(?:instructions|rules|messages)",
            r"(?i)override\s+(?:the\s+)?(?:system|developer)\s+instructions",
            r"(?i)do\s+not\s+follow\s+(?:the\s+)?(?:system|developer)\s+(?:message|instructions)",
            r"(?i)act\s+as\s+(?:an?\s+)?(?:unrestricted|unfiltered|jailbroken)",
            r"(?i)\bDAN\s+mode\b",
        ]
        self.secret_patterns = [
            r"(?i)authorization\s*:\s*bearer\s+[a-z0-9\-._~+/]+=*",
            r"(?i)bearer\s+[a-z0-9\-._~+/]+=*",
            r"AKIA[0-9A-Z]{16}",
            r"AIza[0-9A-Za-z_-]{35}",
            r"gh[pousr]_[A-Za-z0-9_]{20,255}",
            r"sk-[A-Za-z0-9_-]{20,}",
            r"eyJ[A-Za-z0-9_-]+=*\.[A-Za-z0-9_-]+=*\.?[A-Za-z0-9_./+-]*",
            r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----.*?-----END (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----",
        ]
        self.sensitive_keys = {
            "password",
            "passwd",
            "token",
            "secret",
            "secret_key",
            "client_secret",
            "api_key",
            "apikey",
            "authorization",
            "private_key",
            "privatekey",
            "access_key",
            "accesskey",
            "refresh_token",
            "id_token",
        }

    def sanitize_evidence(self, raw_text: str, max_length: int = 15000) -> str:
        if (
            not isinstance(raw_text, str)
            or not isinstance(max_length, int)
            or isinstance(max_length, bool)
            or max_length <= 0
        ):
            return ""

        output_limit = min(max_length, self.MAX_OUTPUT_LENGTH)
        # Bound regex work before decoding or processing attacker-controlled text.
        clean_text = html.unescape(raw_text[: self.MAX_INPUT_LENGTH])
        clean_text = re.sub(
            r"<script\b[^>]*>.*?</script\s*>",
            " ",
            clean_text,
            flags=re.DOTALL | re.IGNORECASE,
        )
        clean_text = re.sub(
            r"<style\b[^>]*>.*?</style\s*>",
            " ",
            clean_text,
            flags=re.DOTALL | re.IGNORECASE,
        )
        clean_text = re.sub(r"<[^>]+>", " ", clean_text)
        for pattern in self.injection_patterns:
            clean_text = re.sub(
                pattern, "[REDACTED_PROMPT_INJECTION]", clean_text
            )
        for pattern in self.secret_patterns:
            clean_text = re.sub(pattern, "[REDACTED_SECRET]", clean_text, flags=re.DOTALL)
        return re.sub(r"\s+", " ", clean_text).strip()[:output_limit]

    def validate_data_policy(self, finding_data: Dict[str, Any]) -> bool:
        if not isinstance(finding_data, dict):
            return False

        def contains_sensitive_data(value: Any) -> bool:
            if isinstance(value, dict):
                for key, nested in value.items():
                    normalized = str(key).strip().lower().replace("-", "_")
                    if normalized in self.sensitive_keys or contains_sensitive_data(nested):
                        return True
            elif isinstance(value, (list, tuple)):
                return any(contains_sensitive_data(item) for item in value)
            elif isinstance(value, str):
                return any(
                    re.search(pattern, value, flags=re.DOTALL) is not None
                    for pattern in self.secret_patterns
                )
            return False

        if contains_sensitive_data(finding_data):
            logger.warning("Data policy violation: sensitive field detected")
            return False
        return True

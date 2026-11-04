import html
import logging
import re
from typing import Any, Dict

logger = logging.getLogger(__name__)


class SecurityGuard:
    """Bounded sanitization and data-policy checks for untrusted AI evidence."""

    MAX_INPUT_LENGTH = 65536
    MAX_OUTPUT_LENGTH = 15000
    MAX_POLICY_NODES = 10000
    MAX_POLICY_VALUE_LENGTH = 65536

    def __init__(self):
        self.injection_patterns = [
            r"(?i)ignore\s+(?:all\s+)?(?:the\s+)?(?:previous|prior|above|earlier)\s+(?:instructions|rules|messages)",
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
            "password_hash",
            "hashed_password",
            "token",
            "access_token",
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
            "refreshtoken",
            "id_token",
            "idtoken",
            "credential",
            "credentials",
            "cookie",
            "set_cookie",
            "session_id",
            "aws_access_key_id",
            "aws_secret_access_key",
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
        """Reject sensitive keys/values and bound traversal of untrusted JSON."""
        if not isinstance(finding_data, dict):
            return False

        pending = [finding_data]
        visited = 0
        while pending:
            visited += 1
            if visited > self.MAX_POLICY_NODES:
                logger.warning("Data policy violation: finding context exceeds node limit")
                return False

            value = pending.pop()
            if isinstance(value, dict):
                for key, nested in value.items():
                    raw_key = str(key).strip()
                    normalized = re.sub(
                        r"([a-z0-9])([A-Z])", r"\1_\2", raw_key
                    ).lower().replace("-", "_")
                    if normalized in self.sensitive_keys:
                        logger.warning("Data policy violation: sensitive field detected")
                        return False
                    pending.append(nested)
            elif isinstance(value, (list, tuple)):
                pending.extend(value)
            elif isinstance(value, str):
                if len(value) > self.MAX_POLICY_VALUE_LENGTH:
                    logger.warning("Data policy violation: field exceeds size limit")
                    return False
                if any(
                    re.search(pattern, value, flags=re.DOTALL) is not None
                    for pattern in self.secret_patterns
                ):
                    logger.warning("Data policy violation: secret-like value detected")
                    return False
        return True

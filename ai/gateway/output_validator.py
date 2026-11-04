import math
from typing import Any, Dict


class OutputValidator:
    REQUIRED_KEYS = {
        "is_true_positive",
        "confidence_score",
        "explanation",
        "remediation",
    }
    MAX_TEXT_LENGTH = 4000

    @staticmethod
    def validate_ai_response(response: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(response, dict):
            raise ValueError("AI response must be a valid dictionary")
        missing = OutputValidator.REQUIRED_KEYS.difference(response.keys())
        if missing:
            raise ValueError(f"AI response missing required keys: {sorted(missing)}")

        # Drop unexpected provider fields so downstream code only receives the
        # explicitly reviewed contract, never arbitrary model-generated metadata.
        result = {key: response[key] for key in OutputValidator.REQUIRED_KEYS}
        if not isinstance(result["is_true_positive"], bool):
            raise ValueError("is_true_positive must be a boolean")
        raw_score = result["confidence_score"]
        if isinstance(raw_score, bool):
            raise ValueError("confidence_score must be numeric")
        try:
            score = float(raw_score)
        except (TypeError, ValueError) as exc:
            raise ValueError("confidence_score must be numeric") from exc
        if not math.isfinite(score):
            raise ValueError("confidence_score must be finite")
        result["confidence_score"] = max(0.0, min(score, 1.0))

        for key in ("explanation", "remediation"):
            value = result[key]
            if not isinstance(value, str):
                raise ValueError(f"{key} must be a string")
            value = value.strip()
            if len(value) > OutputValidator.MAX_TEXT_LENGTH:
                raise ValueError(f"{key} exceeds the maximum length")
            result[key] = value
        return result

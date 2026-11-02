from typing import Any, Dict


class OutputValidator:
    REQUIRED_KEYS = {"is_true_positive", "confidence_score", "explanation", "remediation"}

    @staticmethod
    def validate_ai_response(response: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(response, dict):
            raise ValueError("AI response must be a valid dictionary")
        missing = OutputValidator.REQUIRED_KEYS.difference(response.keys())
        if missing:
            raise ValueError(f"AI response missing required keys: {sorted(missing)}")

        result = dict(response)
        if not isinstance(result["is_true_positive"], bool):
            raise ValueError("is_true_positive must be a boolean")
        try:
            score = float(result["confidence_score"])
        except (TypeError, ValueError) as exc:
            raise ValueError("confidence_score must be numeric") from exc
        if score != score or score in (float("inf"), float("-inf")):
            raise ValueError("confidence_score must be finite")
        result["confidence_score"] = max(0.0, min(score, 1.0))
        for key in ("explanation", "remediation"):
            if not isinstance(result[key], str):
                raise ValueError(f"{key} must be a string")
            result[key] = result[key].strip()
        return result

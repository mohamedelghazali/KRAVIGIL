from typing import Dict, Any

class OutputValidator:
    REQUIRED_KEYS = {"is_true_positive", "confidence_score", "explanation", "remediation"}

    @staticmethod
    def validate_ai_response(response: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(response, dict):
            raise ValueError("AI response must be a dictionary")
            
        if not OutputValidator.REQUIRED_KEYS.issubset(response.keys()):
            missing = OutputValidator.REQUIRED_KEYS - response.keys()
            raise ValueError(f"AI response missing required keys: {missing}")

        if not isinstance(response["is_true_positive"], bool):
            response["is_true_positive"] = False
            
        try:
            score = float(response["confidence_score"])
            response["confidence_score"] = max(0.0, min(score, 1.0))
        except (ValueError, TypeError):
            response["confidence_score"] = 0.0

        return response

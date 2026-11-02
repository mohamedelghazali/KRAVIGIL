from typing import Any, Dict


class BaseAIProvider:
    async def analyze_finding(
        self,
        finding_data: Dict[str, Any],
        evidence_text: str,
    ) -> Dict[str, Any]:
        raise NotImplementedError("Provider must implement analyze_finding")

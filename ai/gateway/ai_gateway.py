from ai.gateway.security_guard import SecurityGuard
from ai.gateway.output_validator import OutputValidator
from ai.providers.gemini_provider import GeminiProvider
from typing import Dict, Any

class AIGateway:
    def __init__(self):
        self.guard = SecurityGuard()
        self.provider = GeminiProvider()

    async def process_finding_analysis(self, finding_data: Dict[str, Any], raw_evidence: str) -> Dict[str, Any]:
        data_class = self.guard.classify_data(finding_data)
        if data_class == "SENSITIVE":
            raise ValueError("Refusing to send sensitive data to external AI provider")

        clean_evidence = self.guard.sanitize_evidence(raw_evidence)
        
        ai_response = await self.provider.analyze_finding(finding_data, clean_evidence)
        
        validated_response = OutputValidator.validate_ai_response(ai_response)
        
        return validated_response

from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseAIProvider(ABC):
    @abstractmethod
    async def analyze_finding(self, finding_data: Dict[str, Any], evidence_text: str) -> Dict[str, Any]:
        pass

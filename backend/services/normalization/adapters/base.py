import subprocess
import json
import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any
from backend.core.exceptions import KravigilException

logger = logging.getLogger(__name__)

class BaseEngineAdapter(ABC):
    def __init__(self, binary_path: str, timeout_seconds: int = 3600):
        self.binary_path = binary_path
        self.timeout_seconds = timeout_seconds

    def execute(self, args: List[str]) -> str:
        try:
            result = subprocess.run(
                [self.binary_path] + args,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False
            )
            
            if result.returncode not in [0, 1]:
                logger.error(f"Engine {self.binary_path} failed with code {result.returncode}: {result.stderr}")
                raise KravigilException(
                    message=f"Engine execution failed: {result.stderr[:500]}",
                    status_code=500,
                    error_code="ENGINE_EXECUTION_ERROR"
                )
                
            return result.stdout
            
        except subprocess.TimeoutExpired:
            logger.error(f"Engine {self.binary_path} timed out after {self.timeout_seconds}s")
            raise KravigilException(
                message="Engine execution timed out",
                status_code=504,
                error_code="ENGINE_TIMEOUT"
            )
        except Exception as e:
            logger.error(f"Failed to execute engine {self.binary_path}: {e}")
            raise KravigilException(
                message=str(e),
                status_code=500,
                error_code="ENGINE_CRASH"
            )

    @abstractmethod
    def parse_output(self, raw_output: str) -> List[Dict[str, Any]]:
        pass

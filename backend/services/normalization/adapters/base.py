import logging
import subprocess
import time
from abc import ABC, abstractmethod
from typing import Callable, List, Dict, Any, Optional

from backend.core.exceptions import KravigilException

logger = logging.getLogger(__name__)


class ScanCancelledError(Exception):
    """Raised when a scan is cancelled while its external engine is running."""


class BaseEngineAdapter(ABC):
    def __init__(self, binary_path: str, timeout_seconds: int = 3600):
        self.binary_path = binary_path
        self.timeout_seconds = timeout_seconds

    @staticmethod
    def _stop_process(process: subprocess.Popen) -> None:
        if process.poll() is not None:
            return
        process.terminate()
        try:
            process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()

    def execute(
        self,
        args: List[str],
        should_cancel: Optional[Callable[[], bool]] = None,
    ) -> str:
        command = [self.binary_path] + args
        process = None
        started_at = time.monotonic()
        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            while True:
                remaining = self.timeout_seconds - (time.monotonic() - started_at)
                if remaining <= 0:
                    self._stop_process(process)
                    raise subprocess.TimeoutExpired(command, self.timeout_seconds)
                try:
                    stdout, stderr = process.communicate(timeout=min(0.5, remaining))
                    break
                except subprocess.TimeoutExpired:
                    if should_cancel is not None and should_cancel():
                        self._stop_process(process)
                        raise ScanCancelledError(
                            f"Engine {self.binary_path} stopped because the scan was cancelled"
                        )

            if process.returncode not in (0, 1):
                logger.error(
                    "Engine %s failed with code %s: %s",
                    self.binary_path,
                    process.returncode,
                    (stderr or "")[:500],
                )
                raise KravigilException(
                    message=f"Engine execution failed: {(stderr or '')[:500]}",
                    status_code=500,
                    error_code="ENGINE_EXECUTION_ERROR",
                )
            return stdout or ""

        except ScanCancelledError:
            raise
        except KravigilException:
            raise
        except subprocess.TimeoutExpired:
            if process is not None:
                self._stop_process(process)
            logger.error(
                "Engine %s timed out after %ss",
                self.binary_path,
                self.timeout_seconds,
            )
            raise KravigilException(
                message="Engine execution timed out",
                status_code=504,
                error_code="ENGINE_TIMEOUT",
            )
        except Exception as exc:
            if process is not None:
                self._stop_process(process)
            logger.exception("Failed to execute engine %s", self.binary_path)
            raise KravigilException(
                message=str(exc),
                status_code=500,
                error_code="ENGINE_CRASH",
            ) from exc

    @abstractmethod
    def parse_output(self, raw_output: str) -> List[Dict[str, Any]]:
        pass

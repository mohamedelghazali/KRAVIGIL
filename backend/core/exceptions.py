import logging
from fastapi import Request
from fastapi.responses import JSONResponse
from datetime import datetime

logger = logging.getLogger(__name__)

class KravigilException(Exception):
    def __init__(self, message: str, status_code: int = 500, error_code: str = "INTERNAL_ERROR"):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        super().__init__(message)

class TenantIsolationException(KravigilException):
    def __init__(self, message: str = "Cross-tenant access denied"):
        super().__init__(message, status_code=403, error_code="TENANT_ISOLATION_VIOLATION")

class ScopeViolationException(KravigilException):
    def __init__(self, message: str = "Target outside authorized scope"):
        super().__init__(message, status_code=403, error_code="SCOPE_VIOLATION")

async def kravigil_exception_handler(request: Request, exc: KravigilException):
    logger.error(f"KravigilException: {exc.error_code} - {exc.message} - Path: {request.url.path}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.error_code,
                "message": exc.message,
                "timestamp": datetime.utcnow().isoformat(),
                "path": str(request.url.path)
            }
        }
    )

async def generic_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {type(exc).__name__} - {str(exc)} - Path: {request.url.path}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred",
                "timestamp": datetime.utcnow().isoformat()
            }
        }
    )

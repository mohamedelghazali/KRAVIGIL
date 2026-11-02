import logging
import redis
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from backend.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, redis_url: str, default_limit: int = 100, window_seconds: int = 60):
        super().__init__(app)
        self.redis = redis.from_url(redis_url, decode_responses=True)
        self.default_limit = default_limit
        self.window_seconds = window_seconds

    async def dispatch(self, request: Request, call_next):
        if request.url.path in ["/health", "/docs", "/openapi.json"]:
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        authorization = request.headers.get("authorization", "")
        tenant_key = "anonymous"
        if authorization.startswith("Bearer "):
            token = authorization.split(" ", 1)[1]
            tenant_key = hash(token) % 100000

        key = f"ratelimit:{tenant_key}:{client_ip}"
        try:
            count = self.redis.get(key)
            if count is None:
                self.redis.setex(key, self.window_seconds, 1)
            elif int(count) >= self.default_limit:
                logger.warning("Rate limit exceeded for IP %s", client_ip)
                raise HTTPException(status_code=429, detail="Too many requests. Please try again later.")
            else:
                self.redis.incr(key)
        except redis.RedisError as exc:
            logger.error("Redis rate limit error: %s", exc)

        return await call_next(request)

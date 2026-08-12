"""
backend/app/middleware/logging.py
──────────────────────────────────
Request/response logging middleware.
Logs every request as structured JSON so you can trace issues
by request_id across the entire log stream.

Log fields:
    - request_id: unique per request (trace across async logs)
    - method, path, status_code, duration_ms
    - user_id if authenticated
"""
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.logger import get_logger

logger = get_logger("http")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Logs every HTTP request with timing and status."""

    # Skip health checks — they'd spam the logs
    SKIP_PATHS = {"/health", "/", "/favicon.ico"}

    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip noisy paths
        if request.url.path in self.SKIP_PATHS:
            return await call_next(request)

        request_id = str(uuid.uuid4())[:8]
        start_time = time.perf_counter()

        # Attach request_id so other parts of the request can log it
        request.state.request_id = request_id

        logger.info(
            f"→ {request.method} {request.url.path}",
            extra={"extra": {
                "request_id": request_id,
                "method":     request.method,
                "path":       request.url.path,
                "query":      str(request.query_params),
                "ip":         request.client.host if request.client else "unknown",
            }}
        )

        response = await call_next(request)

        duration_ms = round((time.perf_counter() - start_time) * 1000, 1)

        log_fn = logger.warning if response.status_code >= 400 else logger.info
        log_fn(
            f"← {response.status_code} {request.method} {request.url.path} ({duration_ms}ms)",
            extra={"extra": {
                "request_id":  request_id,
                "method":      request.method,
                "path":        request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            }}
        )

        # Pass request_id back in response headers (useful for debugging)
        response.headers["X-Request-ID"] = request_id
        return response

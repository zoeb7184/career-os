"""
backend/app/middleware/error_handler.py
────────────────────────────────────────
Global error handler. Catches every NodeError thrown anywhere in the app
and converts it to a structured JSON response.

Response shape (always):
    Success: {"data": <result>,  "error": null}
    Failure: {"data": null,      "error": {"code": "ATS_001", "message": "...", "detail": {}}}

This means frontend and API consumers always know exactly what to check.
"""
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.errors import NodeError
from app.logger import get_logger

logger = get_logger("error_handler")


async def node_error_handler(request: Request, exc: NodeError) -> JSONResponse:
    """Handles all NodeError subclasses — any error from any node."""
    logger.error(
        exc.message,
        extra={"extra": {
            "error_code":  exc.code,
            "status_code": exc.status_code,
            "detail":      exc.detail,
            "path":        str(request.url),
            "method":      request.method,
        }}
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "data":  None,
            "error": exc.to_dict(),
        }
    )


async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handles FastAPI/Pydantic input validation errors (422)."""
    errors = exc.errors()
    logger.warning(
        "Request validation failed",
        extra={"extra": {
            "error_code": "APP_422",
            "path":       str(request.url),
            "errors":     errors,
        }}
    )
    return JSONResponse(
        status_code=422,
        content={
            "data":  None,
            "error": {
                "code":    "APP_422",
                "message": "Request validation failed",
                "detail":  {"errors": errors},
            }
        }
    )


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Catches any exception that wasn't a NodeError.
    In production this prevents leaking stack traces.
    Always logs the full exception for debugging.
    """
    logger.exception(
        f"Unhandled exception: {type(exc).__name__}: {exc}",
        extra={"extra": {
            "error_code": "APP_500",
            "path":       str(request.url),
            "method":     request.method,
        }}
    )
    return JSONResponse(
        status_code=500,
        content={
            "data":  None,
            "error": {
                "code":    "APP_500",
                "message": "An unexpected error occurred. Check logs for details.",
                "detail":  {},
            }
        }
    )

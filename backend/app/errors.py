"""
backend/app/errors.py
──────────────────────
Base error classes for the entire project.
Every node creates its own errors.py that inherits from NodeError.

Pattern:
    # In ml/ats_analyzer/errors.py:
    from app.errors import NodeError

    class ATSParseError(NodeError):
        pass  # error code: ATS_001

    raise ATSParseError(
        code="ATS_001",
        message="Could not parse resume — file may be corrupted",
        detail={"filename": "resume.pdf", "size_bytes": 1024}
    )

The global error handler in middleware/error_handler.py catches NodeError
and returns a structured JSON response automatically.
"""
from typing import Any


class NodeError(Exception):
    """
    Base error for every node in the system.

    Every error that can occur in a node MUST use this class or a subclass.
    Never raise bare Exception — it loses the error code and context.

    Attributes:
        code:    Short code identifying the error. Convention: NODE_NNN
                 Examples: ATS_001, REC_002, FOR_003, ADZ_001
        message: Human-readable description of what went wrong.
        detail:  Optional dict with context (IDs, filenames, counts, etc.)
                 This is logged and included in the API error response.
        status_code: HTTP status to return. Defaults to 500.
    """

    def __init__(
        self,
        code: str,
        message: str,
        detail: dict[str, Any] | None = None,
        status_code: int = 500,
    ) -> None:
        self.code = code
        self.message = message
        self.detail = detail or {}
        self.status_code = status_code
        super().__init__(f"[{code}] {message}")

    def to_dict(self) -> dict[str, Any]:
        """Serialize to the standard API error response shape."""
        return {
            "code":    self.code,
            "message": self.message,
            "detail":  self.detail,
        }


# ── Common shared errors (not node-specific) ──────────────────────

class NotFoundError(NodeError):
    """Resource not found. Maps to HTTP 404."""
    def __init__(self, resource: str, resource_id: str) -> None:
        super().__init__(
            code="APP_404",
            message=f"{resource} not found: {resource_id}",
            detail={"resource": resource, "id": resource_id},
            status_code=404,
        )


class ValidationError(NodeError):
    """Input validation failed. Maps to HTTP 422."""
    def __init__(self, message: str, detail: dict | None = None) -> None:
        super().__init__(
            code="APP_422",
            message=message,
            detail=detail or {},
            status_code=422,
        )


class UnauthorizedError(NodeError):
    """Auth token missing or invalid. Maps to HTTP 401."""
    def __init__(self, message: str = "Authentication required") -> None:
        super().__init__(
            code="APP_401",
            message=message,
            status_code=401,
        )


class ServiceUnavailableError(NodeError):
    """External service (DB, Qdrant, LLM) unreachable. Maps to HTTP 503."""
    def __init__(self, service: str, detail: dict | None = None) -> None:
        super().__init__(
            code="APP_503",
            message=f"Service unavailable: {service}",
            detail=detail or {"service": service},
            status_code=503,
        )

"""Domain error catalog for the mock server.

The real backend defines a much larger error taxonomy.
For mock stability we start with a minimal set and expand only when required.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ErrorCode:
    """Represents a stable error code used in BaseResponse.error.code."""

    code: str
    default_message: str

    def as_error(self, *, message: str | None = None, details: Any | None = None) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": message if message is not None else self.default_message,
            "details": details,
        }


# Generic operational errors
NOT_IMPLEMENTED = ErrorCode(
    code="NOT_IMPLEMENTED",
    default_message="Endpoint is not implemented in the mock yet.",
)

VALIDATION_FAILED = ErrorCode(
    code="VALIDATION_FAILED",
    default_message="Request validation failed.",
)

# "Soft" not-found: we avoid HTTP 404 to keep UI flows from crashing.
NOT_FOUND_SOFT = ErrorCode(
    code="NOT_FOUND_SOFT",
    default_message="Requested entity was not found; mock returned an empty default.",
)


def error_from_exception(exc: Exception) -> dict[str, Any]:
    """Best-effort conversion of unexpected exceptions into a stable error shape.

    The server layer should ensure that unhandled exceptions never propagate as 500.
    """

    return {
        "code": "UNEXPECTED_ERROR",
        "message": "Unexpected error in mock server.",
        "details": {"type": type(exc).__name__, "message": str(exc)},
    }

"""Centralized API Error Handling and Exceptions.

Defines standardized application exceptions and global FastAPI error handlers
ensuring consistent JSON error envelopes across all endpoints.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


def _utc_now_iso() -> str:
    """Return current UTC timestamp in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()


def create_error_payload(
    code: str,
    message: str,
    details: Any = None,
    timestamp_utc: str | None = None,
) -> dict[str, Any]:
    """Generate standardized error response envelope."""
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details if details is not None else {},
            "timestamp_utc": timestamp_utc or _utc_now_iso(),
        }
    }


class TwinException(Exception):
    """Base application exception for Digital Twin backend."""

    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_TWIN_ERROR",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: Any = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}


class AssetNotFoundException(TwinException):
    """Raised when requested transformer asset is not found."""

    def __init__(
        self,
        asset_id: str,
        message: str | None = None,
    ) -> None:
        msg = message or f"Transformer asset '{asset_id}' not found."
        super().__init__(
            message=msg,
            code="ASSET_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
            details={"asset_id": asset_id},
        )


class ResourceNotFoundException(TwinException):
    """Raised when a specific resource or entity is not found."""

    def __init__(
        self,
        resource_type: str,
        resource_id: str,
        message: str | None = None,
    ) -> None:
        msg = message or f"{resource_type} '{resource_id}' not found."
        super().__init__(
            message=msg,
            code="RESOURCE_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
            details={"resource_type": resource_type, "resource_id": resource_id},
        )


class GatedCapabilityException(TwinException):
    """Raised when an operation is requested on an unpromoted or gated capability."""

    def __init__(
        self,
        capability_id: str,
        reason: str,
        required_tier: str | None = None,
    ) -> None:
        msg = f"Capability '{capability_id}' is currently gated: {reason}"
        super().__init__(
            message=msg,
            code="CAPABILITY_GATED",
            status_code=status.HTTP_400_BAD_REQUEST,
            details={
                "capability_id": capability_id,
                "reason": reason,
                "required_tier": required_tier,
            },
        )


HTTP_422_STATUS = getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422)


class ValidationException(TwinException):
    """Raised on application-level validation or prerequisite failure."""

    def __init__(
        self,
        message: str,
        details: Any = None,
    ) -> None:
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            status_code=HTTP_422_STATUS,
            details=details,
        )


class StorageException(TwinException):
    """Raised on storage or query failures."""

    def __init__(
        self,
        message: str,
        details: Any = None,
    ) -> None:
        super().__init__(
            message=message,
            code="STORAGE_ERROR",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details,
        )


class ReplayException(TwinException):
    """Raised on deterministic replay engine errors."""

    def __init__(
        self,
        message: str,
        details: Any = None,
    ) -> None:
        super().__init__(
            message=message,
            code="REPLAY_ERROR",
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
        )


async def twin_exception_handler(request: Request, exc: TwinException) -> JSONResponse:
    """Handle custom application exceptions with standard envelope."""
    payload = create_error_payload(
        code=exc.code,
        message=exc.message,
        details=exc.details,
    )
    return JSONResponse(status_code=exc.status_code, content=payload)


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """Handle FastAPI / Pydantic request validation errors."""
    payload = create_error_payload(
        code="REQUEST_VALIDATION_ERROR",
        message="Request payload failed schema validation.",
        details={"errors": exc.errors()},
    )
    return JSONResponse(
        status_code=HTTP_422_STATUS,
        content=payload,
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle starlette / FastAPI HTTPExceptions."""
    code = "HTTP_ERROR"
    if exc.status_code == status.HTTP_404_NOT_FOUND:
        code = "NOT_FOUND"
    elif exc.status_code == status.HTTP_401_UNAUTHORIZED:
        code = "UNAUTHORIZED"
    elif exc.status_code == status.HTTP_403_FORBIDDEN:
        code = "FORBIDDEN"
    elif exc.status_code == status.HTTP_400_BAD_REQUEST:
        code = "BAD_REQUEST"

    detail_msg = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    payload = create_error_payload(
        code=code,
        message=detail_msg,
        details={"status_code": exc.status_code},
    )
    return JSONResponse(status_code=exc.status_code, content=payload)


from starlette.exceptions import HTTPException as StarletteHTTPException


async def starlette_http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Handle Starlette HTTPExceptions (e.g. 404 Not Found on unknown paths)."""
    code = "HTTP_ERROR"
    if exc.status_code == status.HTTP_404_NOT_FOUND:
        code = "NOT_FOUND"
    elif exc.status_code == status.HTTP_401_UNAUTHORIZED:
        code = "UNAUTHORIZED"
    elif exc.status_code == status.HTTP_403_FORBIDDEN:
        code = "FORBIDDEN"
    elif exc.status_code == status.HTTP_400_BAD_REQUEST:
        code = "BAD_REQUEST"

    detail_msg = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    payload = create_error_payload(
        code=code,
        message=detail_msg,
        details={"status_code": exc.status_code},
    )
    return JSONResponse(status_code=exc.status_code, content=payload)


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected internal exceptions."""
    payload = create_error_payload(
        code="INTERNAL_SERVER_ERROR",
        message="An unexpected internal server error occurred.",
        details={"error_type": type(exc).__name__},
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=payload,
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register all centralized exception handlers on the FastAPI application."""
    app.add_exception_handler(TwinException, twin_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, starlette_http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(HTTPException, http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_exception_handler)


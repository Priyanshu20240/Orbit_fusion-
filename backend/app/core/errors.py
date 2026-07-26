"""Structured error mapping (M7).

A single ``ServiceError`` exception plus a FastAPI exception handler replace
the per-route ``except Exception: raise HTTPException(500, ...)`` pattern.
The handler maps the typed code to a stable HTTP status and a
``{code, message, ...}`` body so the frontend's ``ApiError`` can branch on
``code`` rather than parsing the message string.

Codes / HTTP (per design §C.1.4):
    gee_unavailable       → 503
    no_imagery            → 404
    invalid_request       → 400   # semantic invalidity (engine ValueError)
    validation_error      → 422   # pydantic body validation
    gee_compute_error     → 502
    internal_error        → 500
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


# ── Code → HTTP status table ─────────────────────────────────────────────
_HTTP = {
    "gee_unavailable": 503,
    "no_imagery": 404,
    "invalid_request": 400,
    "validation_error": 422,
    "gee_compute_error": 502,
    "internal_error": 500,
}


class ServiceError(Exception):
    """Typed service error. `code` matches one of _HTTP; the handler maps it
    to a stable HTTP status. `extra` flows into the response body as-is."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        extra: Optional[dict[str, Any]] = None,
    ) -> None:
        if code not in _HTTP:
            raise ValueError(f"unknown ServiceError code: {code!r}")
        super().__init__(message)
        self.code = code
        self.message = message
        self.extra = extra or {}


def _to_status(code: str) -> int:
    return _HTTP.get(code, 500)


async def service_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """FastAPI handler for ``ServiceError``.

    Logs the message at WARNING for 4xx and ERROR for 5xx so the operator
    sees the cause without each test run spamming ERROR for expected 404s.
    """
    if isinstance(exc, ServiceError):
        body = {"code": exc.code, "message": exc.message, **exc.extra}
        status = _to_status(exc.code)
        if status >= 500:
            logger.error("ServiceError %s on %s %s: %s", exc.code, request.method, request.url.path, exc.message)
        else:
            logger.warning("ServiceError %s on %s %s: %s", exc.code, request.method, request.url.path, exc.message)
        return JSONResponse(status_code=status, content=body)
    # Fallback: anything else raised is a 500.
    logger.exception("Unhandled exception in %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"code": "internal_error", "message": "Internal server error"},
    )


def install_error_handlers(app: FastAPI) -> None:
    """Register handlers on the app. Call once from main.py after app = FastAPI(...)."""
    app.add_exception_handler(ServiceError, service_error_handler)

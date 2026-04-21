from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class ApiError(BaseModel):
    code: str
    message: str
    hint: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class ApiEnvelope(BaseModel):
    success: bool
    data: Any | None = None
    error: ApiError | None = None


def ok(data: Any) -> Dict[str, Any]:
    return {"success": True, "data": data, "error": None}


def fail(
    code: str,
    message: str,
    hint: str | None = None,
    details: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    err: Dict[str, Any] = {"code": code, "message": message}
    if hint is not None:
        err["hint"] = hint
    if details is not None:
        err["details"] = details
    return {"success": False, "data": None, "error": err}


class ApiException(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        hint: str | None = None,
        details: Dict[str, Any] | None = None,
    ) -> None:
        self.status_code = int(status_code)
        self.code = str(code)
        self.message = str(message)
        self.hint = hint
        self.details = details
        super().__init__(message)

    def to_error_dict(self) -> Dict[str, Any]:
        err: Dict[str, Any] = {"code": self.code, "message": self.message}
        if self.hint is not None:
            err["hint"] = self.hint
        if self.details is not None:
            err["details"] = self.details
        return err


def _default_error_code_for_status(status_code: int) -> str:
    if status_code in (400, 422):
        return "VALIDATION_ERROR"
    if status_code in (401, 403):
        return "PERMISSION_DENIED"
    if status_code == 404:
        return "NOT_FOUND"
    if status_code == 409:
        return "CONFLICT"
    if status_code >= 500:
        return "INTERNAL_ERROR"
    return "INTERNAL_ERROR"


def _coerce_http_error(exc: HTTPException) -> Dict[str, Any]:
    detail = exc.detail
    if isinstance(detail, dict) and "code" in detail and "message" in detail:
        err: Dict[str, Any] = dict(detail)
        return err

    if isinstance(detail, str) and detail.strip():
        message = detail
    else:
        message = "Request failed"

    return {
        "code": _default_error_code_for_status(int(exc.status_code)),
        "message": message,
    }


def install_api_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiException)
    async def _handle_api_exception(_request: Request, exc: ApiException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"success": False, "data": None, "error": exc.to_error_dict()},
        )

    @app.exception_handler(RequestValidationError)
    async def _handle_validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content=fail("VALIDATION_ERROR", "Validation error", details={"errors": exc.errors()}),
        )

    @app.exception_handler(HTTPException)
    async def _handle_http_exception(_request: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=int(exc.status_code),
            content={"success": False, "data": None, "error": _coerce_http_error(exc)},
        )

    @app.exception_handler(Exception)
    async def _handle_unhandled(_request: Request, _exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content=fail("INTERNAL_ERROR", "Internal server error"),
        )

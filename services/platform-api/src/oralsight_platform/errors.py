"""Safe public errors that never serialize internal exception details."""

from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field


class ErrorDetail(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    code: str
    message: str
    request_id: str = Field(alias="requestId")


class ErrorEnvelope(BaseModel):
    error: ErrorDetail


class ServiceError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        *,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(code)
        self.status_code = status_code
        self.code = code
        self.public_message = message
        self.headers = headers or {}


def request_id(request: Request) -> str:
    value: Any = getattr(request.state, "request_id", None)
    return value if isinstance(value, str) else "request-id-unavailable"


def error_response(request: Request, error: ServiceError) -> JSONResponse:
    payload = ErrorEnvelope(
        error=ErrorDetail(
            code=error.code,
            message=error.public_message,
            requestId=request_id(request),
        )
    )
    return JSONResponse(
        status_code=error.status_code,
        content=payload.model_dump(mode="json", by_alias=True),
        headers=error.headers,
    )

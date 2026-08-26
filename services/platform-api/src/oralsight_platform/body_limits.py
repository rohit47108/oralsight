"""Streaming request-body limits enforced before route parsing or HMAC checks."""

from __future__ import annotations

from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from .config import Settings
from .errors import ServiceError, error_response

MAX_PUBLIC_JSON_BYTES = 2_000_000
MAX_INTERNAL_JSON_BYTES = 2_000_000
MAX_EXPORT_JSON_BYTES = 32_768
MULTIPART_OVERHEAD_BYTES = 1_000_000


class RequestBodyTooLarge(Exception):
    """Stop downstream parsing once the streamed byte budget is exceeded."""


def request_body_limit(path: str, settings: Settings) -> int:
    if path == "/internal/v2/assets/generated":
        return settings.generated_asset_max_bytes + MULTIPART_OVERHEAD_BYTES
    if path == "/internal/v2/exports/render":
        return MAX_EXPORT_JSON_BYTES
    if path.startswith("/internal/v2/"):
        return MAX_INTERNAL_JSON_BYTES
    if path.startswith("/v2/storage/uploads/"):
        return settings.capture_asset_max_bytes
    return MAX_PUBLIC_JSON_BYTES


class RequestBodyLimitMiddleware:
    """Count ASGI request chunks, including bodies without Content-Length."""

    def __init__(self, app: ASGIApp, *, settings: Settings) -> None:
        self.app = app
        self.settings = settings

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("method") not in {
            "POST",
            "PUT",
            "PATCH",
        }:
            await self.app(scope, receive, send)
            return

        limit = request_body_limit(str(scope.get("path", "")), self.settings)
        headers = dict(scope.get("headers", []))
        content_length = headers.get(b"content-length")
        if content_length is not None:
            try:
                declared = int(content_length)
            except ValueError:
                await self._reject(
                    scope,
                    receive,
                    send,
                    400,
                    "invalid_content_length",
                    "Content-Length must be a non-negative integer.",
                )
                return
            if declared < 0:
                await self._reject(
                    scope,
                    receive,
                    send,
                    400,
                    "invalid_content_length",
                    "Content-Length must be a non-negative integer.",
                )
                return
            if declared > limit:
                await self._reject(
                    scope,
                    receive,
                    send,
                    413,
                    "request_too_large",
                    "The request body exceeds the service safety limit.",
                )
                return

        received = 0
        exceeded = False
        downstream_messages: list[Message] = []

        async def limited_receive() -> Message:
            nonlocal exceeded, received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    exceeded = True
                    raise RequestBodyTooLarge
            return message

        async def capture_send(message: Message) -> None:
            downstream_messages.append(message)

        try:
            await self.app(scope, limited_receive, capture_send)
        except RequestBodyTooLarge:
            exceeded = True

        if exceeded:
            await self._reject(
                scope,
                receive,
                send,
                413,
                "request_too_large",
                "The request body exceeds the service safety limit.",
            )
            return
        for message in downstream_messages:
            await send(message)

    @staticmethod
    async def _reject(
        scope: Scope,
        receive: Receive,
        send: Send,
        status_code: int,
        code: str,
        message: str,
    ) -> None:
        request = Request(scope)
        response = error_response(request, ServiceError(status_code, code, message))
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        await response(scope, receive, send)

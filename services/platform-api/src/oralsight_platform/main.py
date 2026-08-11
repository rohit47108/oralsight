"""FastAPI application factory for the OralSight stateful platform service."""

from __future__ import annotations

import logging
import asyncio
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from .config import Settings, get_settings
from .body_limits import RequestBodyLimitMiddleware
from .database import Database
from .errors import ServiceError, error_response
from .job_outbox import job_outbox_loop
from .job_queue import create_job_queue
from .object_storage import create_object_storage
from .routes.account import router as account_router
from .routes.analysis import router as analysis_router
from .routes.analytics import router as analytics_router
from .routes.artifacts import router as artifacts_router
from .routes.capture import router as capture_router
from .routes.clinician import router as clinician_router
from .routes.consent import router as consent_router
from .routes.exports import router as exports_router
from .routes.health import router as health_router
from .routes.internal_assets import router as internal_assets_router
from .routes.internal_jobs import router as internal_jobs_router
from .routes.sharing import router as sharing_router
from .routes.sync import router as sync_router
from .routes.tracking import router as tracking_router
from .retention import retention_loop
from .security import TokenValidator

logger = logging.getLogger("oralsight_platform.safe_access")


def _safe_request_id(value: str | None) -> str:
    if value is not None:
        try:
            parsed = uuid.UUID(value)
        except ValueError:
            pass
        else:
            if parsed.version == 4 and str(parsed) == value:
                return value
    return str(uuid.uuid4())


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    database = Database(resolved_settings)
    object_storage = create_object_storage(resolved_settings)
    job_queue = create_job_queue(resolved_settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if resolved_settings.create_schema_on_start:
            await database.create_schema()
        retention_task = None
        outbox_task = None
        if resolved_settings.retention_sweep_interval_seconds > 0:
            retention_task = asyncio.create_task(retention_loop(app))
        if resolved_settings.queue_dispatch_interval_seconds > 0:
            outbox_task = asyncio.create_task(job_outbox_loop(app))
        yield
        if outbox_task is not None:
            outbox_task.cancel()
            try:
                await outbox_task
            except asyncio.CancelledError:
                pass
        if retention_task is not None:
            retention_task.cancel()
            try:
                await retention_task
            except asyncio.CancelledError:
                pass
        await job_queue.close()
        await object_storage.close()
        await database.dispose()

    app = FastAPI(
        title="OralSight Platform API",
        version=resolved_settings.service_version,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    app.state.settings = resolved_settings
    app.state.database = database
    app.state.object_storage = object_storage
    app.state.job_queue = job_queue
    app.state.token_validator = TokenValidator(resolved_settings)
    app.add_middleware(RequestBodyLimitMiddleware, settings=resolved_settings)

    @app.middleware("http")
    async def privacy_boundary(request: Request, call_next):
        request.state.request_id = _safe_request_id(request.headers.get("x-request-id"))
        started = time.monotonic()
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Request-ID"] = request.state.request_id

        route = request.scope.get("route")
        route_template = getattr(route, "path", "<unmatched>")
        duration_ms = round((time.monotonic() - started) * 1000)
        # Deliberate allowlist: no body, query, headers, subject, token, key, or result.
        logger.info(
            "request_complete method=%s route=%s status=%s duration_ms=%s request_id=%s",
            request.method,
            route_template,
            response.status_code,
            duration_ms,
            request.state.request_id,
        )
        return response

    @app.exception_handler(ServiceError)
    async def service_error_handler(request: Request, exc: ServiceError):
        return error_response(request, exc)

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, _exc: RequestValidationError):
        return error_response(
            request,
            ServiceError(
                422,
                "invalid_request",
                "The request does not match the endpoint contract.",
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(request: Request, exc: StarletteHTTPException):
        if exc.status_code == 404:
            error = ServiceError(404, "not_found", "Endpoint not found.")
        elif exc.status_code == 405:
            error = ServiceError(405, "method_not_allowed", "Method not allowed.")
        else:
            error = ServiceError(
                exc.status_code,
                "http_error",
                "The request could not be completed.",
            )
        return error_response(request, error)

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception):
        # Exception messages and tracebacks may contain tokens or submitted fields.
        # Log only the exception class and the generated request identifier.
        logger.error(
            "unhandled_error type=%s request_id=%s",
            type(exc).__name__,
            request.state.request_id,
        )
        return error_response(
            request,
            ServiceError(
                500,
                "internal_error",
                "The service could not complete the request.",
            ),
        )

    app.include_router(health_router)
    app.include_router(account_router)
    app.include_router(capture_router)
    app.include_router(consent_router)
    app.include_router(analysis_router)
    app.include_router(analytics_router)
    app.include_router(tracking_router)
    app.include_router(artifacts_router)
    app.include_router(sync_router)
    app.include_router(clinician_router)
    app.include_router(exports_router)
    app.include_router(sharing_router)
    app.include_router(internal_assets_router)
    app.include_router(internal_jobs_router)
    return app


app = create_app()


def run() -> None:
    import uvicorn

    uvicorn.run(
        "oralsight_platform.main:app",
        host="0.0.0.0",
        port=8080,
        access_log=False,
    )

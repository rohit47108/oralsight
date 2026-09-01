from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ..database import Database
from ..schemas import HealthResponse, ReadinessResponse

router = APIRouter(tags=["service"])


@router.get("/healthz", response_model=HealthResponse)
async def healthz(request: Request) -> HealthResponse:
    settings = request.app.state.settings
    return HealthResponse(
        service=settings.service_name,
        version=settings.service_version,
    )


@router.get("/readyz", response_model=ReadinessResponse)
async def readyz(request: Request):
    database: Database = request.app.state.database
    database_ready = True
    try:
        await database.ping()
    except Exception:  # noqa: BLE001 - readiness must safely collapse every DB failure
        database_ready = False
    queue_ready = await request.app.state.job_queue.ping()
    storage_ready = await request.app.state.object_storage.ping()
    if not (database_ready and queue_ready and storage_ready):
        payload = ReadinessResponse(
            status="not_ready",
            database="ready" if database_ready else "unavailable",
            queue="ready" if queue_ready else "unavailable",
            object_storage="ready" if storage_ready else "unavailable",
        )
        return JSONResponse(
            status_code=503,
            content=payload.model_dump(mode="json", by_alias=True),
        )
    return ReadinessResponse(
        status="ready", database="ready", queue="ready", object_storage="ready"
    )

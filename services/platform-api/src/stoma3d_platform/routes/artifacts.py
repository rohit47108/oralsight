"""Owner-scoped report artifacts and durable product jobs."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Request, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..dependencies import Actor, get_current_actor, get_session
from ..artifact_files import report_filename
from ..errors import ServiceError
from ..idempotency import (
    commit_idempotent,
    find_replay,
    request_sha256,
    validate_idempotency_key,
)
from ..models import (
    AnalysisRun,
    CandidateObservation,
    CaptureAsset,
    CaptureSet,
    CaptureView,
    Job,
    JobStatus,
    JobType,
    LesionRecord,
    ReportArtifact,
    ScanSession,
    utc_now,
)
from ..job_orchestration import (
    build_job_envelope,
    envelope_json,
    publish_job,
    validate_owned_job_payload,
)
from ..job_queue import QueueUnavailable
from ..object_storage import StorageError, StorageNotFound
from ..product_schemas import (
    JobCreate,
    JobList,
    JobResponse,
    ReportCreate,
    ReportList,
    ReportResponse,
)
from .capture import _owned

router = APIRouter(prefix="/v2", tags=["artifacts"])


def _report_response(value: ReportArtifact) -> ReportResponse:
    return ReportResponse(
        report_artifact_id=value.id,
        patient_id=value.user_id,
        scan_session_ids=value.scan_session_ids,
        format=value.report_format,
        asset_id=value.asset_id,
        sha256=value.content_sha256,
        byte_size=value.byte_size,
        locale=value.locale,
        accessible=value.accessible,
        input_origins=value.input_origins,
        analysis_origins=value.analysis_origins,
        model_versions=value.model_versions,
        signed_envelope_id=value.signed_envelope_id,
        created_at=value.created_at,
        retention_expires_at=value.retention_expires_at,
    )


def _public_job_type(value: JobType) -> JobType:
    return JobType.ACCOUNT_DELETION if value is JobType.DELETE_ALL else value


def _job_response(value: Job) -> JobResponse:
    expires_at = value.expires_at or value.created_at + timedelta(days=30)
    return JobResponse(
        job_id=value.id,
        owner_id=value.user_id,
        type=_public_job_type(value.job_type),
        status=value.status,
        input_refs=value.input_refs,
        output_refs=value.output_refs,
        progress=value.progress_percent / 100,
        attempt=value.attempt_count,
        max_attempts=value.max_attempts,
        error_code=value.error_code,
        error_message=value.error_message,
        created_at=value.created_at,
        started_at=value.started_at,
        completed_at=value.completed_at,
        expires_at=expires_at,
        outcome=value.result_outcome,
        reason_code=value.reason_code,
        result=value.result_payload,
        cancellation_requested=value.cancellation_requested_at is not None,
    )


async def _validate_owned_refs(
    session: AsyncSession, user_id: str, resource_ids: list[str]
) -> None:
    if not resource_ids:
        return
    requested = set(resource_ids)
    owned: set[str] = set()
    for model in [
        ScanSession,
        CaptureSet,
        CaptureView,
        CaptureAsset,
        AnalysisRun,
        CandidateObservation,
        LesionRecord,
        ReportArtifact,
    ]:
        owned.update(
            await session.scalars(
                select(model.id).where(
                    model.user_id == user_id,
                    model.id.in_(requested),
                )
            )
        )
    if requested != owned:
        raise ServiceError(
            404, "resource_not_found", "The requested resource was not found."
        )


@router.post(
    "/reports", response_model=ReportResponse, status_code=status.HTTP_201_CREATED
)
async def create_report(
    body: ReportCreate,
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
    idempotency_header: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> ReportResponse:
    key = validate_idempotency_key(idempotency_header)
    digest = request_sha256(body)
    scope = "v2.reports.create"
    replay = await find_replay(
        session,
        user_id=actor.user_id,
        scope=scope,
        key=key,
        digest=digest,
        response_model=ReportResponse,
    )
    if replay:
        return replay
    for scan_id in body.scan_session_ids:
        await _owned(session, ScanSession, scan_id, actor.user_id)
    now = utc_now()
    if body.retention_expires_at and body.retention_expires_at <= now:
        raise ServiceError(
            422,
            "invalid_retention_expiry",
            "Report retention expiry must be in the future.",
        )
    value = ReportArtifact(
        user_id=actor.user_id,
        scan_session_ids=body.scan_session_ids,
        report_format=body.format,
        asset_id=body.asset_id,
        content_sha256=body.sha256,
        byte_size=body.byte_size,
        locale=body.locale,
        accessible=body.accessible,
        input_origins=[origin.value for origin in body.input_origins],
        analysis_origins=[origin.value for origin in body.analysis_origins],
        model_versions=body.model_versions,
        signed_envelope_id=body.signed_envelope_id,
        retention_expires_at=body.retention_expires_at,
    )
    session.add(value)
    await session.flush()
    response = _report_response(value)
    return await commit_idempotent(
        session,
        user_id=actor.user_id,
        scope=scope,
        key=key,
        digest=digest,
        response=response,
        response_status=201,
    )


@router.get("/reports/{report_id}", response_model=ReportResponse)
async def get_report(
    report_id: str,
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ReportResponse:
    value = await _owned(session, ReportArtifact, report_id, actor.user_id)
    return _report_response(value)


@router.get("/reports/{report_id}/content")
async def get_report_content(
    report_id: str,
    request: Request,
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    value = await _owned(session, ReportArtifact, report_id, actor.user_id)
    if not value.object_key:
        raise ServiceError(
            410, "report_content_unavailable", "The report content is unavailable."
        )
    try:
        data = await request.app.state.object_storage.get_bytes(
            value.object_key, max_bytes=value.byte_size
        )
    except StorageNotFound as exc:
        raise ServiceError(
            410, "report_content_unavailable", "The report content is unavailable."
        ) from exc
    except StorageError as exc:
        raise ServiceError(
            503, "object_storage_unavailable", "Storage is unavailable."
        ) from exc
    if (
        len(data) != value.byte_size
        or hashlib.sha256(data).hexdigest() != value.content_sha256
    ):
        raise ServiceError(
            500, "stored_report_corrupt", "The stored report failed verification."
        )
    return Response(
        content=data,
        media_type=value.media_type,
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": (
                f'inline; filename="{report_filename(value.id, value.media_type)}"'
            ),
        },
    )


@router.get("/reports", response_model=ReportList)
async def list_reports(
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    before: Annotated[datetime | None, Query()] = None,
) -> ReportList:
    query = select(ReportArtifact).where(
        ReportArtifact.user_id == actor.user_id,
        ReportArtifact.deleted_at.is_(None),
    )
    if before is not None:
        query = query.where(ReportArtifact.created_at < before)
    rows = list(
        await session.scalars(
            query.order_by(
                ReportArtifact.created_at.desc(), ReportArtifact.id.desc()
            ).limit(limit + 1)
        )
    )
    has_more = len(rows) > limit
    rows = rows[:limit]
    cursor = (
        rows[-1].created_at.astimezone(UTC).isoformat() if has_more and rows else None
    )
    return ReportList(
        items=[_report_response(value) for value in rows], next_cursor=cursor
    )


@router.post("/jobs", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(
    body: JobCreate,
    request: Request,
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
    idempotency_header: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> JobResponse:
    key = validate_idempotency_key(idempotency_header)
    digest = request_sha256(body)
    scope = "v2.jobs.create"
    replay = await find_replay(
        session,
        user_id=actor.user_id,
        scope=scope,
        key=key,
        digest=digest,
        response_model=JobResponse,
    )
    if replay:
        stored = await session.get(Job, replay.job_id)
        if stored is None or stored.user_id != actor.user_id:
            raise ServiceError(500, "invalid_job_state", "The job is incomplete.")
        await publish_job(request.app, session, stored)
        return replay
    payload, derived_refs, asset_ids = await validate_owned_job_payload(
        session,
        user_id=actor.user_id,
        job_type=body.type,
        raw_payload=body.payload,
    )
    if body.input_refs and set(body.input_refs) != set(derived_refs):
        raise ServiceError(
            422,
            "job_input_refs_mismatch",
            "Job input references must exactly match the validated payload.",
        )
    now = utc_now()
    value = Job(
        user_id=actor.user_id,
        job_type=body.type,
        status=JobStatus.QUEUED,
        input_refs=derived_refs,
        output_refs=[],
        max_attempts=body.max_attempts,
        expires_at=now + timedelta(hours=24),
        request_payload=payload,
    )
    session.add(value)
    await session.flush()
    envelope = build_job_envelope(
        value, request_id=request.state.request_id, asset_ids=asset_ids
    )
    value.queue_envelope = envelope_json(envelope)
    response = _job_response(value)
    response = await commit_idempotent(
        session,
        user_id=actor.user_id,
        scope=scope,
        key=key,
        digest=digest,
        response=response,
        response_status=201,
    )
    await publish_job(request.app, session, value)
    return response


@router.get("/jobs", response_model=JobList)
async def list_jobs(
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    before: Annotated[datetime | None, Query()] = None,
) -> JobList:
    query = select(Job).where(Job.user_id == actor.user_id)
    if before is not None:
        query = query.where(Job.created_at < before)
    rows = list(
        await session.scalars(
            query.order_by(Job.created_at.desc(), Job.id.desc()).limit(limit + 1)
        )
    )
    has_more = len(rows) > limit
    rows = rows[:limit]
    cursor = (
        rows[-1].created_at.astimezone(UTC).isoformat() if has_more and rows else None
    )
    return JobList(items=[_job_response(value) for value in rows], next_cursor=cursor)


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str,
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> JobResponse:
    value = await _owned(session, Job, job_id, actor.user_id)
    return _job_response(value)


@router.post("/jobs/{job_id}/cancel", response_model=JobResponse)
async def cancel_job(
    job_id: str,
    request: Request,
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> JobResponse:
    value = await _owned(session, Job, job_id, actor.user_id)
    terminal = {
        JobStatus.SUCCEEDED,
        JobStatus.FAILED,
        JobStatus.CANCELLED,
        JobStatus.EXPIRED,
    }
    if value.status in terminal:
        return _job_response(value)
    now = utc_now()
    ttl = max(
        60, int(((value.expires_at or now + timedelta(hours=24)) - now).total_seconds())
    )
    try:
        await request.app.state.job_queue.cancel(value.id, ttl_seconds=ttl)
    except QueueUnavailable as exc:
        raise ServiceError(
            503, "job_queue_unavailable", "The cancellation could not be delivered."
        ) from exc
    value.cancellation_requested_at = now
    value.status = JobStatus.CANCELLED
    value.result_outcome = "cancelled"
    value.reason_code = "user_cancelled"
    value.completed_at = now
    await session.commit()
    return _job_response(value)

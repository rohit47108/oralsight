"""Explicit versioned consent records used by scans and report jobs."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..collaboration_common import append_audit_event
from ..consent_schemas import (
    ConsentCreate,
    ConsentDocumentResponse,
    ConsentList,
    ConsentResponse,
    ConsentRevoke,
)
from ..dependencies import Actor, get_current_actor, get_session
from ..errors import ServiceError
from ..idempotency import (
    commit_idempotent,
    find_replay,
    request_sha256,
    validate_idempotency_key,
)
from ..models import (
    AccessGrantStatus,
    ClinicianAccessGrant,
    ConsentRecord,
    Device,
    Job,
    JobStatus,
    JobType,
    ShareLink,
    ShareLinkStatus,
    utc_now,
)
from ..product_consent import (
    BODY,
    DOCUMENT_ID,
    DOCUMENT_SHA256,
    DOCUMENT_VERSION,
    TITLE,
)

router = APIRouter(prefix="/v2", tags=["product consent"])


def _response(value: ConsentRecord) -> ConsentResponse:
    return ConsentResponse(
        consent_record_id=value.id,
        document_id=value.document_id,
        document_version=value.document_version,
        document_sha256=value.document_sha256,
        accepted=value.accepted,
        accepted_at=value.accepted_at,
        revoked_at=value.revoked_at,
        active=value.accepted and value.revoked_at is None,
    )


@router.get("/consent-documents/current", response_model=ConsentDocumentResponse)
async def get_current_consent_document() -> ConsentDocumentResponse:
    return ConsentDocumentResponse(
        document_id=DOCUMENT_ID,
        document_version=DOCUMENT_VERSION,
        document_sha256=DOCUMENT_SHA256,
        title=TITLE,
        body=BODY,
    )


@router.get("/consents", response_model=ConsentList)
async def list_consents(
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ConsentList:
    rows = list(
        await session.scalars(
            select(ConsentRecord)
            .where(ConsentRecord.user_id == actor.user_id)
            .order_by(ConsentRecord.accepted_at.desc(), ConsentRecord.id.desc())
        )
    )
    return ConsentList(items=[_response(value) for value in rows])


@router.post(
    "/consents",
    response_model=ConsentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_consent(
    body: ConsentCreate,
    request: Request,
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
    idempotency_header: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> ConsentResponse:
    key = validate_idempotency_key(idempotency_header)
    digest = request_sha256(body)
    scope = "v2.consents.create"
    replay = await find_replay(
        session,
        user_id=actor.user_id,
        scope=scope,
        key=key,
        digest=digest,
        response_model=ConsentResponse,
    )
    if replay:
        return replay
    if body.device_id is not None:
        device = await session.get(Device, body.device_id)
        if device is None or device.user_id != actor.user_id or device.revoked_at:
            raise ServiceError(
                404, "resource_not_found", "The requested device was not found."
            )
    if (
        body.document_id != DOCUMENT_ID
        or body.document_version != DOCUMENT_VERSION
        or body.document_sha256 != DOCUMENT_SHA256
    ):
        raise ServiceError(
            409,
            "consent_document_outdated",
            "Refresh the consent document before continuing.",
        )
    existing = await session.scalar(
        select(ConsentRecord).where(
            ConsentRecord.user_id == actor.user_id,
            ConsentRecord.document_id == body.document_id,
            ConsentRecord.document_version == body.document_version,
            ConsentRecord.document_sha256 == body.document_sha256,
            ConsentRecord.revoked_at.is_(None),
        )
    )
    if existing is not None:
        raise ServiceError(
            409,
            "consent_version_already_recorded",
            "This consent version is already recorded.",
        )
    now = utc_now()
    value = ConsentRecord(
        user_id=actor.user_id,
        device_id=body.device_id,
        document_id=body.document_id,
        document_version=body.document_version,
        document_sha256=body.document_sha256,
        accepted=True,
        accepted_at=now,
    )
    session.add(value)
    await session.flush()
    append_audit_event(
        session,
        patient_user_id=actor.user_id,
        actor_user_id=actor.user_id,
        event_type="consent.accepted",
        resource_type="consent_record",
        resource_id=value.id,
        request_id=request.state.request_id,
        details={
            "documentId": value.document_id,
            "documentVersion": value.document_version,
        },
    )
    response = _response(value)
    return await commit_idempotent(
        session,
        user_id=actor.user_id,
        scope=scope,
        key=key,
        digest=digest,
        response=response,
        response_status=201,
    )


@router.post("/consents/{consent_record_id}/revoke", response_model=ConsentResponse)
async def revoke_consent(
    consent_record_id: str,
    body: ConsentRevoke,
    request: Request,
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
    idempotency_header: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> ConsentResponse:
    key = validate_idempotency_key(idempotency_header)
    digest = request_sha256(body)
    scope = f"v2.consents.{consent_record_id}.revoke"
    replay = await find_replay(
        session,
        user_id=actor.user_id,
        scope=scope,
        key=key,
        digest=digest,
        response_model=ConsentResponse,
    )
    if replay:
        return replay
    value = await session.get(ConsentRecord, consent_record_id)
    if value is None or value.user_id != actor.user_id:
        raise ServiceError(
            404, "resource_not_found", "The consent record was not found."
        )
    jobs: list[Job] = []
    if value.revoked_at is None:
        now = utc_now()
        value.revoked_at = now
        jobs = list(
            await session.scalars(
                select(Job).where(
                    Job.user_id == actor.user_id,
                    Job.status.in_([JobStatus.QUEUED, JobStatus.RUNNING]),
                    Job.job_type.not_in([JobType.ACCOUNT_DELETION, JobType.DELETE_ALL]),
                )
            )
        )
        for job in jobs:
            job.cancellation_requested_at = now
            job.status = JobStatus.CANCELLED
            job.result_outcome = "cancelled"
            job.reason_code = "consent_withdrawn"
            job.completed_at = now
        shares = list(
            await session.scalars(
                select(ShareLink).where(
                    ShareLink.patient_user_id == actor.user_id,
                    ShareLink.status == ShareLinkStatus.ACTIVE,
                )
            )
        )
        for share in shares:
            share.status = ShareLinkStatus.REVOKED
            share.revoked_at = now
        grants = list(
            await session.scalars(
                select(ClinicianAccessGrant).where(
                    ClinicianAccessGrant.patient_user_id == actor.user_id,
                    ClinicianAccessGrant.status == AccessGrantStatus.ACTIVE,
                )
            )
        )
        for grant in grants:
            grant.status = AccessGrantStatus.REVOKED
            grant.revoked_at = now
        append_audit_event(
            session,
            patient_user_id=actor.user_id,
            actor_user_id=actor.user_id,
            event_type="consent.revoked",
            resource_type="consent_record",
            resource_id=value.id,
            request_id=request.state.request_id,
            details={
                "documentId": value.document_id,
                "documentVersion": value.document_version,
            },
        )
    response = _response(value)
    response = await commit_idempotent(
        session,
        user_id=actor.user_id,
        scope=scope,
        key=key,
        digest=digest,
        response=response,
        response_status=200,
    )
    for job in jobs:
        try:
            await request.app.state.job_queue.cancel(job.id, ttl_seconds=86_400)
        except Exception:  # cancellation state is already durable and authoritative
            pass
    return response

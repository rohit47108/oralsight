"""Authenticated account identity and delete-all lifecycle endpoints."""

from __future__ import annotations

import hashlib
import hmac
import json
import re
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..collaboration_common import keyed_digest
from ..dependencies import (
    Actor,
    get_account_actor,
    get_session,
    get_token_claims,
)
from ..deletion_tombstones import (
    current_deleted_subject_fingerprint,
    matching_tombstone,
)
from ..errors import ServiceError
from ..job_contracts import DeleteAllPayload
from ..job_orchestration import build_job_envelope, envelope_json, publish_job
from ..models import (
    AuditEvent,
    AccessGrantStatus,
    CaptureAsset,
    ClinicianAccessGrant,
    ConsentRecord,
    DeletionRequest,
    DeletedSubjectTombstone,
    DeletionStatus,
    IdempotencyRecord,
    Job,
    JobStatus,
    JobType,
    ShareExchangeToken,
    ShareLink,
    ShareLinkStatus,
    User,
    UserRole,
    UserStatus,
    utc_now,
)
from ..schemas import (
    AccountRecreationRequest,
    AccountRecreationResponse,
    DeletionRequestCreate,
    DeletionRequestResponse,
    MeResponse,
)
from ..security import TokenClaims

router = APIRouter(prefix="/v2/me", tags=["account"])
IDEMPOTENCY_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{16,128}$")
DELETE_SCOPE = "v2.me.delete_all"


def _deletion_response(value: DeletionRequest) -> DeletionRequestResponse:
    return DeletionRequestResponse(
        request_id=value.id,
        job_id=value.job_id,
        status=value.status,
        requested_at=value.requested_at,
        started_at=value.started_at,
        completed_at=value.completed_at,
        error_code=value.error_code,
    )


def _request_hash(body: DeletionRequestCreate) -> str:
    canonical = json.dumps(
        body.model_dump(mode="json", by_alias=True),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _validate_idempotency_key(value: str | None) -> str:
    if value is None or IDEMPOTENCY_PATTERN.fullmatch(value) is None:
        raise ServiceError(
            400,
            "invalid_idempotency_key",
            "Idempotency-Key must be 16 to 128 safe ASCII characters.",
        )
    return value


@router.get("", response_model=MeResponse)
async def get_me(
    actor: Annotated[Actor, Depends(get_account_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> MeResponse:
    user = await session.get(User, actor.user_id)
    if user is None:
        raise ServiceError(404, "account_not_found", "The account was not found.")
    required_oidc_role = (
        user.role if user.role in {UserRole.CLINICIAN, UserRole.ADMIN} else None
    )
    return MeResponse(
        id=user.id,
        role=user.role,
        status=user.status,
        created_at=user.created_at,
        deletion_pending=user.status is UserStatus.DELETION_PENDING,
        required_oidc_role=required_oidc_role,
        privileged_access_ready=(
            required_oidc_role is None or required_oidc_role.value in actor.token_roles
        ),
        clinician_application_eligible=(
            user.role is UserRole.PATIENT
            and not actor.token_roles.isdisjoint(
                {
                    UserRole.CLINICIAN_PENDING.value,
                    UserRole.CLINICIAN.value,
                }
            )
        ),
    )


@router.post(
    "/deletion-requests",
    response_model=DeletionRequestResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def request_delete_all(
    body: DeletionRequestCreate,
    request: Request,
    actor: Annotated[Actor, Depends(get_account_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
    idempotency_header: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> DeletionRequestResponse:
    idempotency_key = _validate_idempotency_key(idempotency_header)
    request_sha256 = _request_hash(body)

    existing_record = await session.scalar(
        select(IdempotencyRecord).where(
            IdempotencyRecord.user_id == actor.user_id,
            IdempotencyRecord.scope == DELETE_SCOPE,
            IdempotencyRecord.idempotency_key == idempotency_key,
        )
    )
    if existing_record is not None:
        if existing_record.request_sha256 != request_sha256:
            raise ServiceError(
                409,
                "idempotency_conflict",
                "This idempotency key was already used for a different request.",
            )
        response = DeletionRequestResponse.model_validate(
            existing_record.response_payload
        )
        existing_job = await session.get(Job, response.job_id)
        if existing_job is None or existing_job.user_id != actor.user_id:
            raise ServiceError(500, "invalid_job_state", "The job is incomplete.")
        await publish_job(request.app, session, existing_job)
        return response

    user = await session.scalar(
        select(User)
        .where(User.id == actor.user_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if user is None:
        raise ServiceError(404, "account_not_found", "The account was not found.")

    pending = await session.scalar(
        select(DeletionRequest).where(
            DeletionRequest.user_id == actor.user_id,
            DeletionRequest.status.in_(
                [DeletionStatus.REQUESTED, DeletionStatus.IN_PROGRESS]
            ),
        )
    )
    if pending is not None:
        raise ServiceError(
            409,
            "deletion_already_pending",
            "A delete-all request is already in progress.",
        )

    now = utc_now()
    cancelled_jobs = list(
        await session.scalars(
            select(Job).where(
                Job.user_id == user.id,
                Job.status.in_([JobStatus.QUEUED, JobStatus.RUNNING]),
                Job.job_type.not_in([JobType.ACCOUNT_DELETION, JobType.DELETE_ALL]),
            )
        )
    )
    for pending_job in cancelled_jobs:
        pending_job.cancellation_requested_at = now
        pending_job.status = JobStatus.CANCELLED
        pending_job.result_outcome = "cancelled"
        pending_job.reason_code = "account_deletion_pending"
        pending_job.completed_at = now

    active_consents = list(
        await session.scalars(
            select(ConsentRecord)
            .where(
                ConsentRecord.user_id == user.id,
                ConsentRecord.accepted.is_(True),
                ConsentRecord.revoked_at.is_(None),
            )
            .with_for_update()
        )
    )
    for consent in active_consents:
        consent.revoked_at = now

    owned_shares = list(
        await session.scalars(
            select(ShareLink)
            .where(ShareLink.patient_user_id == user.id)
            .with_for_update()
        )
    )
    share_ids = [share.id for share in owned_shares]
    for share in owned_shares:
        if share.status is ShareLinkStatus.ACTIVE or share.revoked_at is None:
            share.status = ShareLinkStatus.REVOKED
            share.revoked_at = now
    active_exchange_tokens = (
        list(
            await session.scalars(
                select(ShareExchangeToken)
                .where(
                    ShareExchangeToken.share_id.in_(share_ids),
                    ShareExchangeToken.revoked_at.is_(None),
                )
                .with_for_update()
            )
        )
        if share_ids
        else []
    )
    for token in active_exchange_tokens:
        token.revoked_at = now

    active_grants = list(
        await session.scalars(
            select(ClinicianAccessGrant)
            .where(
                or_(
                    ClinicianAccessGrant.patient_user_id == user.id,
                    ClinicianAccessGrant.clinician_user_id == user.id,
                ),
                ClinicianAccessGrant.status == AccessGrantStatus.ACTIVE,
            )
            .with_for_update()
        )
    )
    for grant in active_grants:
        grant.status = AccessGrantStatus.REVOKED
        grant.revoked_at = now

    job = Job(
        user_id=user.id,
        job_type=JobType.DELETE_ALL,
        status=JobStatus.QUEUED,
        max_attempts=5,
        expires_at=now + timedelta(hours=24),
    )
    session.add(job)
    await session.flush()

    deletion = DeletionRequest(
        user_id=user.id,
        job_id=job.id,
        subject_fingerprint=keyed_digest(
            request.app.state.settings, "deletion-status-subject", user.oidc_subject
        ),
        status=DeletionStatus.REQUESTED,
        requested_at=now,
    )
    session.add(deletion)
    await session.flush()
    tombstone_fingerprint = current_deleted_subject_fingerprint(
        request.app.state.settings, user.oidc_subject
    )
    tombstone = await session.scalar(
        select(DeletedSubjectTombstone)
        .where(DeletedSubjectTombstone.subject_fingerprint == tombstone_fingerprint)
        .with_for_update()
    )
    if tombstone is None:
        session.add(
            DeletedSubjectTombstone(
                subject_fingerprint=tombstone_fingerprint,
                fingerprint_key_version=request.app.state.settings.deletion_tombstone_current_key_version,
                first_deleted_at=now,
                last_deleted_at=now,
            )
        )
    else:
        tombstone.last_deleted_at = now
    job.resource_id = deletion.id
    deletion_payload = DeleteAllPayload(
        deletion_request_id=deletion.id,
        subject_account_id=user.id,
    )
    job.request_payload = deletion_payload.model_dump(mode="json", by_alias=True)
    asset_ids = list(
        await session.scalars(
            select(CaptureAsset.id).where(
                CaptureAsset.user_id == user.id,
                CaptureAsset.deleted_at.is_(None),
            )
        )
    )
    job.input_refs = [deletion.id, *asset_ids]
    job.queue_envelope = envelope_json(
        build_job_envelope(
            job,
            request_id=request.state.request_id,
            asset_ids=asset_ids,
        )
    )
    user.status = UserStatus.DELETION_PENDING

    response = _deletion_response(deletion)
    session.add_all(
        [
            AuditEvent(
                user_id=user.id,
                actor_user_id=user.id,
                event_type="delete_all.requested",
                resource_type="deletion_request",
                resource_id=deletion.id,
                request_id=request.state.request_id,
                details={"status": DeletionStatus.REQUESTED.value},
            ),
            IdempotencyRecord(
                user_id=user.id,
                scope=DELETE_SCOPE,
                idempotency_key=idempotency_key,
                request_sha256=request_sha256,
                response_status=status.HTTP_202_ACCEPTED,
                response_payload=response.model_dump(mode="json", by_alias=True),
                created_at=now,
                expires_at=now + timedelta(hours=48),
            ),
        ]
    )
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        replay = await session.scalar(
            select(IdempotencyRecord).where(
                IdempotencyRecord.user_id == actor.user_id,
                IdempotencyRecord.scope == DELETE_SCOPE,
                IdempotencyRecord.idempotency_key == idempotency_key,
            )
        )
        if replay is not None and replay.request_sha256 == request_sha256:
            response = DeletionRequestResponse.model_validate(replay.response_payload)
            existing_job = await session.get(Job, response.job_id)
            if existing_job is None or existing_job.user_id != actor.user_id:
                raise ServiceError(500, "invalid_job_state", "The job is incomplete.")
            await publish_job(request.app, session, existing_job)
            return response
        raise ServiceError(
            409,
            "request_conflict",
            "The request conflicted with another account operation.",
        ) from exc
    await publish_job(request.app, session, job)
    for cancelled_job in cancelled_jobs:
        try:
            await request.app.state.job_queue.cancel(
                cancelled_job.id, ttl_seconds=86_400
            )
        except Exception:  # durable cancellation remains authoritative
            pass
    return response


recreation_router = APIRouter(prefix="/v2", tags=["account"])


def _recreation_account(user: User, claims: TokenClaims) -> MeResponse:
    required = user.role if user.role in {UserRole.CLINICIAN, UserRole.ADMIN} else None
    return MeResponse(
        id=user.id,
        role=user.role,
        status=user.status,
        created_at=user.created_at,
        deletion_pending=False,
        required_oidc_role=required,
        privileged_access_ready=required is None or required.value in claims.roles,
        clinician_application_eligible=user.role is UserRole.PATIENT
        and not claims.roles.isdisjoint(
            {UserRole.CLINICIAN_PENDING.value, UserRole.CLINICIAN.value}
        ),
    )


@recreation_router.post(
    "/account-recreations", response_model=AccountRecreationResponse
)
async def recreate_account(
    body: AccountRecreationRequest,
    claims: Annotated[TokenClaims, Depends(get_token_claims)],
    session: Annotated[AsyncSession, Depends(get_session)],
    request: Request,
) -> AccountRecreationResponse:
    tombstone = await matching_tombstone(
        session, request.app.state.settings, claims.subject, lock=True
    )
    if tombstone is None:
        raise ServiceError(
            409, "recreation_not_required", "No deleted account requires recreation."
        )
    existing = await session.scalar(
        select(User).where(User.oidc_subject == claims.subject)
    )
    if existing is None:
        existing = User(oidc_subject=claims.subject, role=UserRole.PATIENT)
        session.add(existing)
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            existing = await session.scalar(
                select(User).where(User.oidc_subject == claims.subject)
            )
            if existing is None:
                raise
    return AccountRecreationResponse(
        account=_recreation_account(existing, claims), recreated_after_deletion=True
    )


@router.get(
    "/deletion-requests/{deletion_request_id}",
    response_model=DeletionRequestResponse,
)
async def get_delete_all_status(
    deletion_request_id: str,
    request: Request,
    claims: Annotated[TokenClaims, Depends(get_token_claims)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DeletionRequestResponse:
    value = await session.get(DeletionRequest, deletion_request_id)
    if value is None:
        raise ServiceError(
            404, "deletion_request_not_found", "The deletion request was not found."
        )
    expected_fingerprint = keyed_digest(
        request.app.state.settings, "deletion-status-subject", claims.subject
    )
    if value.subject_fingerprint is None or not hmac.compare_digest(
        value.subject_fingerprint, expected_fingerprint
    ):
        # Do not provision a new account and do not disclose another user's request.
        raise ServiceError(
            404, "resource_not_found", "The requested resource was not found."
        )
    return _deletion_response(value)

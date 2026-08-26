"""Clinician verification, patient grants, review queue, and access history."""

from __future__ import annotations

import hashlib
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Request, status
from fastapi.responses import Response
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..collaboration_common import (
    GRANT_DEFAULT_LIFETIME,
    GRANT_MAX_LIFETIME,
    LONG_RECORD_RETENTION,
    append_access_event,
    append_audit_event,
    as_utc,
    grant_response,
    history_item,
    is_future,
    keyed_digest,
    require_owned_resource,
    resource_view_response,
    review_response,
    verification_response,
)
from ..artifact_files import report_filename
from ..collaboration_schemas import (
    AccessGrantCreate,
    AccessGrantList,
    AccessGrantResponse,
    AccessHistoryResponse,
    ClinicianReviewQueue,
    ClinicianReviewResponse,
    ClinicianReviewStatusUpdate,
    ClinicianVerificationCreate,
    ClinicianVerificationDecision,
    ClinicianVerificationQueue,
    ClinicianVerificationResponse,
    ResourceRef,
    ResourceViewResponse,
    ReviewAnnotationCreate,
    ReviewAnnotationResponse,
)
from ..dependencies import (
    Actor,
    get_current_actor,
    get_session,
    require_oidc_roles,
)
from ..errors import ServiceError
from ..idempotency import (
    commit_idempotent,
    find_replay,
    request_sha256,
    validate_idempotency_key,
)
from ..models import (
    AccessActorType,
    AccessEvent,
    AccessEventType,
    AccessGrantResource,
    AccessGrantStatus,
    CandidateObservation,
    CaptureAsset,
    CaptureStatus,
    CaptureView,
    ClinicianAccessGrant,
    ClinicianReview,
    ClinicianReviewStatus,
    ClinicianVerification,
    ClinicianVerificationStatus,
    ReviewAnnotation,
    ReportArtifact,
    ShareResourceType,
    User,
    UserRole,
    UserStatus,
    utc_now,
)
from ..object_storage import StorageError, StorageNotFound

router = APIRouter(prefix="/v2", tags=["clinician collaboration"])


def _application_claim_allowed(actor: Actor) -> bool:
    return not actor.token_roles.isdisjoint({"clinician_pending", "clinician"})


async def _owned_grant(
    session: AsyncSession, grant_id: str, patient_user_id: str
) -> ClinicianAccessGrant:
    value = await session.get(ClinicianAccessGrant, grant_id)
    if value is None or value.patient_user_id != patient_user_id:
        raise ServiceError(
            404, "resource_not_found", "The requested resource was not found."
        )
    return value


async def _clinician_review(
    session: AsyncSession,
    review_id: str,
    actor: Actor,
    *,
    require_active: bool = True,
) -> tuple[ClinicianReview, ClinicianAccessGrant]:
    review = await session.get(ClinicianReview, review_id)
    if review is None or review.clinician_user_id != actor.user_id:
        raise ServiceError(
            404, "resource_not_found", "The requested resource was not found."
        )
    grant = await session.get(ClinicianAccessGrant, review.grant_id)
    if grant is None:
        raise ServiceError(500, "invalid_review_state", "The review is incomplete.")
    if require_active and (
        grant.status is not AccessGrantStatus.ACTIVE
        or grant.revoked_at is not None
        or not is_future(grant.expires_at)
    ):
        raise ServiceError(
            410, "access_grant_inactive", "Patient access is no longer active."
        )
    return review, grant


async def _resource_is_granted(
    session: AsyncSession, grant_id: str, resource: ResourceRef
) -> bool:
    value = await session.scalar(
        select(AccessGrantResource.id).where(
            AccessGrantResource.grant_id == grant_id,
            AccessGrantResource.resource_type == resource.resource_type,
            AccessGrantResource.resource_id == resource.resource_id,
        )
    )
    return value is not None


@router.post(
    "/clinician-verifications",
    response_model=ClinicianVerificationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def submit_clinician_verification(
    body: ClinicianVerificationCreate,
    request: Request,
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
    idempotency_header: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> ClinicianVerificationResponse:
    key = validate_idempotency_key(idempotency_header)
    digest = request_sha256(body)
    scope = "v2.clinician_verifications.create"
    replay = await find_replay(
        session,
        user_id=actor.user_id,
        scope=scope,
        key=key,
        digest=digest,
        response_model=ClinicianVerificationResponse,
    )
    if replay:
        return replay
    if not _application_claim_allowed(actor):
        raise ServiceError(
            403,
            "oidc_role_required",
            "The access token is not authorized for clinician verification.",
        )
    user = await session.scalar(
        select(User).where(User.id == actor.user_id).with_for_update()
    )
    if user is None:
        raise ServiceError(404, "account_not_found", "The account was not found.")
    if user.status is not UserStatus.ACTIVE:
        raise ServiceError(403, "account_not_active", "This account is not available.")
    if user.role is not UserRole.PATIENT:
        raise ServiceError(
            409,
            "invalid_verification_state",
            "The clinician application cannot change this account role.",
        )
    existing = await session.scalar(
        select(ClinicianVerification)
        .where(
            ClinicianVerification.user_id == actor.user_id,
            ClinicianVerification.status.in_(
                [
                    ClinicianVerificationStatus.PENDING,
                    ClinicianVerificationStatus.VERIFIED,
                ]
            ),
        )
        .order_by(ClinicianVerification.submitted_at.desc())
    )
    if existing is not None:
        raise ServiceError(
            409,
            "verification_already_active",
            "A pending or verified clinician record already exists.",
        )
    now = utc_now()
    value = ClinicianVerification(
        user_id=actor.user_id,
        status=ClinicianVerificationStatus.PENDING,
        profession=body.profession,
        license_jurisdiction=body.license_jurisdiction,
        license_number_sha256=keyed_digest(
            request.app.state.settings, "clinician-license", body.license_number
        ),
        license_number_suffix=body.license_number[-4:],
        organization=body.organization,
        applicant_evidence_ref=body.applicant_evidence_ref,
        submitted_at=now,
        retention_expires_at=now + LONG_RECORD_RETENTION,
    )
    user.role = UserRole.CLINICIAN_PENDING
    session.add(value)
    await session.flush()
    append_audit_event(
        session,
        patient_user_id=actor.user_id,
        actor_user_id=actor.user_id,
        event_type="clinician_verification.submitted",
        resource_type="clinician_verification",
        resource_id=value.id,
        request_id=request.state.request_id,
        details={"status": ClinicianVerificationStatus.PENDING.value},
    )
    response = verification_response(
        value,
        required_claim=request.app.state.settings.oidc_role_claim,
        applicant_role=user.role,
        applicant_token_roles=actor.token_roles,
    )
    return await commit_idempotent(
        session,
        user_id=actor.user_id,
        scope=scope,
        key=key,
        digest=digest,
        response=response,
        response_status=201,
    )


@router.get(
    "/clinician-verifications/current",
    response_model=ClinicianVerificationResponse,
)
async def get_current_clinician_verification(
    request: Request,
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ClinicianVerificationResponse:
    value = await session.scalar(
        select(ClinicianVerification)
        .where(ClinicianVerification.user_id == actor.user_id)
        .order_by(ClinicianVerification.submitted_at.desc())
    )
    if value is None:
        raise ServiceError(
            404, "verification_not_found", "No clinician verification was found."
        )
    return verification_response(
        value,
        required_claim=request.app.state.settings.oidc_role_claim,
        applicant_role=actor.role,
        applicant_token_roles=actor.token_roles,
    )


@router.post(
    "/clinician-verifications/current/activate",
    response_model=ClinicianVerificationResponse,
)
async def activate_current_clinician_verification(
    request: Request,
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ClinicianVerificationResponse:
    if UserRole.CLINICIAN.value not in actor.token_roles:
        raise ServiceError(
            403,
            "oidc_role_required",
            "The access token is not authorized for the clinician role.",
        )
    value = await session.scalar(
        select(ClinicianVerification)
        .where(
            ClinicianVerification.user_id == actor.user_id,
            ClinicianVerification.status == ClinicianVerificationStatus.VERIFIED,
        )
        .order_by(ClinicianVerification.submitted_at.desc())
        .with_for_update()
    )
    if value is None:
        raise ServiceError(
            409,
            "verification_not_ready",
            "An approved clinician verification is required.",
        )
    user = await session.scalar(
        select(User).where(User.id == actor.user_id).with_for_update()
    )
    if user is None:
        raise ServiceError(404, "account_not_found", "The account was not found.")
    if user.status is not UserStatus.ACTIVE:
        raise ServiceError(403, "account_not_active", "This account is not available.")
    if user.role not in {UserRole.CLINICIAN_PENDING, UserRole.CLINICIAN}:
        raise ServiceError(
            409,
            "invalid_verification_state",
            "The clinician account state cannot be activated.",
        )

    if value.oidc_role_observed_at is None:
        value.oidc_role_observed_at = utc_now()
        append_audit_event(
            session,
            patient_user_id=actor.user_id,
            actor_user_id=actor.user_id,
            event_type="clinician_verification.oidc_role_observed",
            resource_type="clinician_verification",
            resource_id=value.id,
            request_id=request.state.request_id,
            details={"requiredRole": UserRole.CLINICIAN.value},
        )
    if user.role is UserRole.CLINICIAN_PENDING:
        user.role = UserRole.CLINICIAN
    await session.commit()
    return verification_response(
        value,
        required_claim=request.app.state.settings.oidc_role_claim,
        applicant_role=user.role,
        applicant_token_roles=actor.token_roles,
    )


@router.get(
    "/admin/clinician-verifications",
    response_model=ClinicianVerificationQueue,
)
async def list_clinician_verifications(
    request: Request,
    actor: Annotated[Actor, Depends(require_oidc_roles(UserRole.ADMIN))],
    session: Annotated[AsyncSession, Depends(get_session)],
    verification_status: Annotated[
        ClinicianVerificationStatus | None, Query(alias="status")
    ] = ClinicianVerificationStatus.PENDING,
    cursor: Annotated[str | None, Query(min_length=1, max_length=36)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ClinicianVerificationQueue:
    del actor
    statement = select(ClinicianVerification)
    if verification_status is not None:
        statement = statement.where(ClinicianVerification.status == verification_status)
    if cursor:
        cursor_value = await session.get(ClinicianVerification, cursor)
        if cursor_value is None:
            raise ServiceError(400, "invalid_cursor", "The queue cursor is invalid.")
        statement = statement.where(
            or_(
                ClinicianVerification.submitted_at < cursor_value.submitted_at,
                (ClinicianVerification.submitted_at == cursor_value.submitted_at)
                & (ClinicianVerification.id < cursor_value.id),
            )
        )
    rows = list(
        await session.scalars(
            statement.order_by(
                ClinicianVerification.submitted_at.desc(),
                ClinicianVerification.id.desc(),
            ).limit(limit + 1)
        )
    )
    page = rows[:limit]
    return ClinicianVerificationQueue(
        items=[
            verification_response(
                value,
                required_claim=request.app.state.settings.oidc_role_claim,
            )
            for value in page
        ],
        next_cursor=page[-1].id if len(rows) > limit else None,
    )


@router.get(
    "/admin/clinician-verifications/{verification_id}",
    response_model=ClinicianVerificationResponse,
)
async def get_clinician_verification_for_admin(
    verification_id: str,
    request: Request,
    actor: Annotated[Actor, Depends(require_oidc_roles(UserRole.ADMIN))],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ClinicianVerificationResponse:
    del actor
    value = await session.get(ClinicianVerification, verification_id)
    if value is None:
        raise ServiceError(
            404, "resource_not_found", "The requested resource was not found."
        )
    return verification_response(
        value,
        required_claim=request.app.state.settings.oidc_role_claim,
    )


@router.post(
    "/admin/clinician-verifications/{verification_id}/decision",
    response_model=ClinicianVerificationResponse,
)
async def decide_clinician_verification(
    verification_id: str,
    body: ClinicianVerificationDecision,
    request: Request,
    actor: Annotated[Actor, Depends(require_oidc_roles(UserRole.ADMIN))],
    session: Annotated[AsyncSession, Depends(get_session)],
    idempotency_header: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> ClinicianVerificationResponse:
    key = validate_idempotency_key(idempotency_header)
    digest = request_sha256(body)
    scope = f"v2.clinician_verification.{verification_id}.decision"
    replay = await find_replay(
        session,
        user_id=actor.user_id,
        scope=scope,
        key=key,
        digest=digest,
        response_model=ClinicianVerificationResponse,
    )
    if replay:
        return replay
    value = await session.scalar(
        select(ClinicianVerification)
        .where(ClinicianVerification.id == verification_id)
        .with_for_update()
    )
    if value is None:
        raise ServiceError(
            404, "resource_not_found", "The requested resource was not found."
        )
    if value.status is not ClinicianVerificationStatus.PENDING:
        raise ServiceError(
            409, "verification_already_decided", "This verification is already final."
        )
    now = utc_now()
    if as_utc(body.evidence.checked_at) > now + timedelta(minutes=5):
        raise ServiceError(
            422, "invalid_review_evidence", "Review evidence cannot be future dated."
        )
    applicant = await session.scalar(
        select(User).where(User.id == value.user_id).with_for_update()
    )
    if applicant is None:
        raise ServiceError(
            500, "invalid_verification_state", "The applicant is missing."
        )
    if (
        applicant.status is not UserStatus.ACTIVE
        or applicant.role is not UserRole.CLINICIAN_PENDING
    ):
        raise ServiceError(
            409,
            "invalid_verification_state",
            "The clinician decision cannot change this account role.",
        )
    value.status = body.status
    value.reviewer_user_id = actor.user_id
    value.reviewer_evidence = body.evidence.model_dump(mode="json", by_alias=True)
    value.decision_reason = body.decision_reason
    value.reviewed_at = now
    if body.status is ClinicianVerificationStatus.REJECTED:
        applicant.role = UserRole.PATIENT
    append_audit_event(
        session,
        patient_user_id=value.user_id,
        actor_user_id=actor.user_id,
        event_type="clinician_verification.decided",
        resource_type="clinician_verification",
        resource_id=value.id,
        request_id=request.state.request_id,
        details={"status": body.status.value},
    )
    response = verification_response(
        value,
        required_claim=request.app.state.settings.oidc_role_claim,
        applicant_role=applicant.role,
    )
    return await commit_idempotent(
        session,
        user_id=actor.user_id,
        scope=scope,
        key=key,
        digest=digest,
        response=response,
        response_status=200,
    )


@router.post(
    "/access-grants",
    response_model=AccessGrantResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_access_grant(
    body: AccessGrantCreate,
    request: Request,
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
    idempotency_header: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> AccessGrantResponse:
    key = validate_idempotency_key(idempotency_header)
    digest = request_sha256(body)
    scope = "v2.access_grants.create"
    replay = await find_replay(
        session,
        user_id=actor.user_id,
        scope=scope,
        key=key,
        digest=digest,
        response_model=AccessGrantResponse,
    )
    if replay:
        return replay
    if body.clinician_user_id == actor.user_id:
        raise ServiceError(
            422, "invalid_clinician", "An access grant requires another account."
        )
    clinician = await session.get(User, body.clinician_user_id)
    if (
        clinician is None
        or clinician.role is not UserRole.CLINICIAN
        or clinician.status is not UserStatus.ACTIVE
    ):
        raise ServiceError(
            404, "clinician_not_found", "A verified clinician was not found."
        )
    verified = await session.scalar(
        select(ClinicianVerification.id).where(
            ClinicianVerification.user_id == clinician.id,
            ClinicianVerification.status == ClinicianVerificationStatus.VERIFIED,
        )
    )
    if verified is None:
        raise ServiceError(
            404, "clinician_not_found", "A verified clinician was not found."
        )
    for resource in body.resources:
        await require_owned_resource(
            session, patient_user_id=actor.user_id, resource=resource
        )
    now = utc_now()
    expires_at = (
        as_utc(body.expires_at) if body.expires_at else now + GRANT_DEFAULT_LIFETIME
    )
    if expires_at <= now or expires_at > now + GRANT_MAX_LIFETIME:
        raise ServiceError(
            422,
            "invalid_grant_expiry",
            "Grant expiry must be in the future and no more than one year away.",
        )
    retention_expires_at = now + LONG_RECORD_RETENTION
    grant = ClinicianAccessGrant(
        patient_user_id=actor.user_id,
        clinician_user_id=clinician.id,
        status=AccessGrantStatus.ACTIVE,
        label=body.label,
        expires_at=expires_at,
        retention_expires_at=retention_expires_at,
    )
    session.add(grant)
    await session.flush()
    session.add_all(
        [
            AccessGrantResource(
                grant_id=grant.id,
                resource_type=resource.resource_type,
                resource_id=resource.resource_id,
            )
            for resource in body.resources
        ]
    )
    review = ClinicianReview(
        grant_id=grant.id,
        patient_user_id=actor.user_id,
        clinician_user_id=clinician.id,
        status=ClinicianReviewStatus.PENDING,
        retention_expires_at=retention_expires_at,
    )
    session.add(review)
    await session.flush()
    append_access_event(
        session,
        patient_user_id=actor.user_id,
        actor_user_id=actor.user_id,
        actor_type=AccessActorType.PATIENT,
        event_type=AccessEventType.GRANT_CREATED,
        resource_type="access_grant",
        resource_id=grant.id,
        grant_id=grant.id,
        review_id=review.id,
        request_id=request.state.request_id,
        details={"resourceCount": len(body.resources)},
    )
    response = await grant_response(session, grant)
    return await commit_idempotent(
        session,
        user_id=actor.user_id,
        scope=scope,
        key=key,
        digest=digest,
        response=response,
        response_status=201,
    )


@router.get("/access-grants", response_model=AccessGrantList)
async def list_access_grants(
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AccessGrantList:
    rows = list(
        await session.scalars(
            select(ClinicianAccessGrant)
            .where(ClinicianAccessGrant.patient_user_id == actor.user_id)
            .order_by(
                ClinicianAccessGrant.created_at.desc(), ClinicianAccessGrant.id.desc()
            )
        )
    )
    return AccessGrantList(
        items=[await grant_response(session, value) for value in rows]
    )


@router.get("/access-grants/{grant_id}", response_model=AccessGrantResponse)
async def get_access_grant(
    grant_id: str,
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AccessGrantResponse:
    return await grant_response(
        session, await _owned_grant(session, grant_id, actor.user_id)
    )


@router.post("/access-grants/{grant_id}/revoke", response_model=AccessGrantResponse)
async def revoke_access_grant(
    grant_id: str,
    request: Request,
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
    idempotency_header: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> AccessGrantResponse:
    key = validate_idempotency_key(idempotency_header)
    body = ResourceRef(resource_type="scan_session", resource_id=grant_id)
    digest = request_sha256(body)
    scope = f"v2.access_grant.{grant_id}.revoke"
    replay = await find_replay(
        session,
        user_id=actor.user_id,
        scope=scope,
        key=key,
        digest=digest,
        response_model=AccessGrantResponse,
    )
    if replay:
        return replay
    grant = await _owned_grant(session, grant_id, actor.user_id)
    if grant.revoked_at is None:
        grant.status = AccessGrantStatus.REVOKED
        grant.revoked_at = utc_now()
        review = await session.scalar(
            select(ClinicianReview).where(ClinicianReview.grant_id == grant.id)
        )
        append_access_event(
            session,
            patient_user_id=actor.user_id,
            actor_user_id=actor.user_id,
            actor_type=AccessActorType.PATIENT,
            event_type=AccessEventType.GRANT_REVOKED,
            resource_type="access_grant",
            resource_id=grant.id,
            grant_id=grant.id,
            review_id=review.id if review else None,
            request_id=request.state.request_id,
        )
    response = await grant_response(session, grant)
    return await commit_idempotent(
        session,
        user_id=actor.user_id,
        scope=scope,
        key=key,
        digest=digest,
        response=response,
        response_status=200,
    )


@router.get("/clinician/reviews", response_model=ClinicianReviewQueue)
async def list_clinician_reviews(
    actor: Annotated[Actor, Depends(require_oidc_roles(UserRole.CLINICIAN))],
    session: Annotated[AsyncSession, Depends(get_session)],
    review_status: Annotated[
        ClinicianReviewStatus | None, Query(alias="status")
    ] = None,
    cursor: Annotated[str | None, Query(min_length=1, max_length=36)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ClinicianReviewQueue:
    now = utc_now()
    statement = (
        select(ClinicianReview)
        .join(
            ClinicianAccessGrant,
            ClinicianReview.grant_id == ClinicianAccessGrant.id,
        )
        .where(
            ClinicianReview.clinician_user_id == actor.user_id,
            ClinicianAccessGrant.status == AccessGrantStatus.ACTIVE,
            ClinicianAccessGrant.revoked_at.is_(None),
            ClinicianAccessGrant.expires_at > now,
        )
    )
    if review_status is not None:
        statement = statement.where(ClinicianReview.status == review_status)
    if cursor:
        cursor_value = await session.get(ClinicianReview, cursor)
        if cursor_value is None or cursor_value.clinician_user_id != actor.user_id:
            raise ServiceError(400, "invalid_cursor", "The queue cursor is invalid.")
        statement = statement.where(
            or_(
                ClinicianReview.created_at < cursor_value.created_at,
                (ClinicianReview.created_at == cursor_value.created_at)
                & (ClinicianReview.id < cursor_value.id),
            )
        )
    rows = list(
        await session.scalars(
            statement.order_by(
                ClinicianReview.created_at.desc(), ClinicianReview.id.desc()
            ).limit(limit + 1)
        )
    )
    page = rows[:limit]
    return ClinicianReviewQueue(
        items=[await review_response(session, value) for value in page],
        next_cursor=page[-1].id if len(rows) > limit else None,
    )


@router.get("/clinician/reviews/{review_id}", response_model=ClinicianReviewResponse)
async def get_clinician_review(
    review_id: str,
    actor: Annotated[Actor, Depends(require_oidc_roles(UserRole.CLINICIAN))],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ClinicianReviewResponse:
    review, _grant = await _clinician_review(session, review_id, actor)
    return await review_response(session, review)


@router.get(
    "/clinician/reviews/{review_id}/resources/{resource_type}/{resource_id}",
    response_model=ResourceViewResponse,
)
async def get_clinician_review_resource(
    review_id: str,
    resource_type: str,
    resource_id: str,
    request: Request,
    actor: Annotated[Actor, Depends(require_oidc_roles(UserRole.CLINICIAN))],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ResourceViewResponse:
    try:
        resource = ResourceRef(resource_type=resource_type, resource_id=resource_id)
    except ValueError as exc:
        raise ServiceError(
            404, "resource_not_found", "The requested resource was not found."
        ) from exc
    review, grant = await _clinician_review(session, review_id, actor)
    if not await _resource_is_granted(session, grant.id, resource):
        raise ServiceError(
            404, "resource_not_found", "The requested resource was not found."
        )
    response = await resource_view_response(
        session, patient_user_id=review.patient_user_id, resource=resource
    )
    append_access_event(
        session,
        patient_user_id=review.patient_user_id,
        actor_user_id=actor.user_id,
        actor_type=AccessActorType.CLINICIAN,
        event_type=AccessEventType.RESOURCE_VIEWED,
        resource_type=resource.resource_type.value,
        resource_id=resource.resource_id,
        grant_id=grant.id,
        review_id=review.id,
        request_id=request.state.request_id,
    )
    await session.commit()
    return response


@router.get("/clinician/reviews/{review_id}/resources/report/{report_id}/content")
async def get_clinician_report_content(
    review_id: str,
    report_id: str,
    request: Request,
    actor: Annotated[Actor, Depends(require_oidc_roles(UserRole.CLINICIAN))],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    resource = ResourceRef(resource_type="report", resource_id=report_id)
    review, grant = await _clinician_review(session, review_id, actor)
    if not await _resource_is_granted(session, grant.id, resource):
        raise ServiceError(
            404, "resource_not_found", "The requested resource was not found."
        )
    report = await session.get(ReportArtifact, report_id)
    if (
        report is None
        or report.user_id != review.patient_user_id
        or report.deleted_at is not None
        or not report.object_key
    ):
        raise ServiceError(
            404, "resource_not_found", "The requested resource was not found."
        )
    try:
        data = await request.app.state.object_storage.get_bytes(
            report.object_key, max_bytes=report.byte_size
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
        len(data) != report.byte_size
        or hashlib.sha256(data).hexdigest() != report.content_sha256
    ):
        raise ServiceError(
            500, "stored_report_corrupt", "The stored report failed verification."
        )
    append_access_event(
        session,
        patient_user_id=review.patient_user_id,
        actor_user_id=actor.user_id,
        actor_type=AccessActorType.CLINICIAN,
        event_type=AccessEventType.RESOURCE_VIEWED,
        resource_type="report_content",
        resource_id=report.id,
        grant_id=grant.id,
        review_id=review.id,
        request_id=request.state.request_id,
    )
    await session.commit()
    return Response(
        content=data,
        media_type=report.media_type,
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": (
                f'inline; filename="{report_filename(report.id, report.media_type)}"'
            ),
        },
    )


@router.get("/clinician/reviews/{review_id}/capture-views/{capture_view_id}/content")
async def get_clinician_capture_view_content(
    review_id: str,
    capture_view_id: str,
    request: Request,
    actor: Annotated[Actor, Depends(require_oidc_roles(UserRole.CLINICIAN))],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    """Return one image only when its analysis run is in this active grant."""

    review, grant = await _clinician_review(session, review_id, actor)
    granted_analysis_id = await session.scalar(
        select(CandidateObservation.analysis_run_id)
        .join(
            AccessGrantResource,
            and_(
                AccessGrantResource.grant_id == grant.id,
                AccessGrantResource.resource_type == ShareResourceType.ANALYSIS_RUN,
                AccessGrantResource.resource_id == CandidateObservation.analysis_run_id,
            ),
        )
        .where(
            CandidateObservation.capture_view_id == capture_view_id,
            CandidateObservation.user_id == review.patient_user_id,
        )
        .limit(1)
    )
    if granted_analysis_id is None:
        raise ServiceError(
            404, "resource_not_found", "The requested resource was not found."
        )
    await require_owned_resource(
        session,
        patient_user_id=review.patient_user_id,
        resource=ResourceRef(
            resource_type=ShareResourceType.ANALYSIS_RUN,
            resource_id=granted_analysis_id,
        ),
    )

    capture_view = await session.get(CaptureView, capture_view_id)
    if (
        capture_view is None
        or capture_view.user_id != review.patient_user_id
        or capture_view.deleted_at is not None
    ):
        raise ServiceError(
            404, "resource_not_found", "The requested resource was not found."
        )
    asset = await session.get(CaptureAsset, capture_view.asset_id)
    if (
        asset is None
        or asset.user_id != review.patient_user_id
        or asset.deleted_at is not None
        or asset.status is not CaptureStatus.AVAILABLE
        or asset.media_type not in {"image/jpeg", "image/png", "image/webp"}
    ):
        raise ServiceError(
            404, "resource_not_found", "The requested resource was not found."
        )
    try:
        data = await request.app.state.object_storage.get_bytes(
            asset.object_key, max_bytes=asset.byte_size
        )
    except StorageNotFound as exc:
        raise ServiceError(
            410,
            "capture_content_unavailable",
            "The capture image is unavailable.",
        ) from exc
    except StorageError as exc:
        raise ServiceError(
            503, "object_storage_unavailable", "Storage is unavailable."
        ) from exc
    if (
        len(data) != asset.byte_size
        or hashlib.sha256(data).hexdigest() != asset.content_sha256
    ):
        raise ServiceError(
            500, "stored_asset_corrupt", "The stored image failed verification."
        )
    append_access_event(
        session,
        patient_user_id=review.patient_user_id,
        actor_user_id=actor.user_id,
        actor_type=AccessActorType.CLINICIAN,
        event_type=AccessEventType.RESOURCE_VIEWED,
        resource_type="capture_view_content",
        resource_id=capture_view.id,
        grant_id=grant.id,
        review_id=review.id,
        request_id=request.state.request_id,
        details={"analysisRunId": granted_analysis_id},
    )
    await session.commit()
    return Response(
        content=data,
        media_type=asset.media_type,
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": "inline",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post(
    "/clinician/reviews/{review_id}/status",
    response_model=ClinicianReviewResponse,
)
async def update_clinician_review_status(
    review_id: str,
    body: ClinicianReviewStatusUpdate,
    request: Request,
    actor: Annotated[Actor, Depends(require_oidc_roles(UserRole.CLINICIAN))],
    session: Annotated[AsyncSession, Depends(get_session)],
    idempotency_header: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> ClinicianReviewResponse:
    key = validate_idempotency_key(idempotency_header)
    digest = request_sha256(body)
    scope = f"v2.clinician_review.{review_id}.status"
    replay = await find_replay(
        session,
        user_id=actor.user_id,
        scope=scope,
        key=key,
        digest=digest,
        response_model=ClinicianReviewResponse,
    )
    if replay:
        return replay
    review, grant = await _clinician_review(session, review_id, actor)
    current = review.status
    allowed = {
        ClinicianReviewStatus.PENDING: {
            ClinicianReviewStatus.IN_REVIEW,
            ClinicianReviewStatus.DECLINED,
        },
        ClinicianReviewStatus.IN_REVIEW: {
            ClinicianReviewStatus.COMPLETED,
            ClinicianReviewStatus.DECLINED,
        },
        ClinicianReviewStatus.COMPLETED: set(),
        ClinicianReviewStatus.DECLINED: set(),
    }
    changed = body.status is not current
    if changed and body.status not in allowed[current]:
        raise ServiceError(
            409,
            "invalid_review_transition",
            "This review status change is not allowed.",
        )
    if changed:
        now = utc_now()
        review.status = body.status
        review.summary = body.summary
        if body.status is ClinicianReviewStatus.IN_REVIEW:
            review.started_at = now
        if body.status in {
            ClinicianReviewStatus.COMPLETED,
            ClinicianReviewStatus.DECLINED,
        }:
            review.completed_at = now
        append_access_event(
            session,
            patient_user_id=review.patient_user_id,
            actor_user_id=actor.user_id,
            actor_type=AccessActorType.CLINICIAN,
            event_type=AccessEventType.REVIEW_STATUS_CHANGED,
            resource_type="clinician_review",
            resource_id=review.id,
            grant_id=grant.id,
            review_id=review.id,
            request_id=request.state.request_id,
            details={"status": body.status.value},
        )
    response = await review_response(session, review)
    return await commit_idempotent(
        session,
        user_id=actor.user_id,
        scope=scope,
        key=key,
        digest=digest,
        response=response,
        response_status=200,
    )


@router.post(
    "/clinician/reviews/{review_id}/annotations",
    response_model=ReviewAnnotationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_review_annotation(
    review_id: str,
    body: ReviewAnnotationCreate,
    request: Request,
    actor: Annotated[Actor, Depends(require_oidc_roles(UserRole.CLINICIAN))],
    session: Annotated[AsyncSession, Depends(get_session)],
    idempotency_header: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> ReviewAnnotationResponse:
    key = validate_idempotency_key(idempotency_header)
    digest = request_sha256(body)
    scope = f"v2.clinician_review.{review_id}.annotations"
    replay = await find_replay(
        session,
        user_id=actor.user_id,
        scope=scope,
        key=key,
        digest=digest,
        response_model=ReviewAnnotationResponse,
    )
    if replay:
        return replay
    review, grant = await _clinician_review(session, review_id, actor)
    if not await _resource_is_granted(session, grant.id, body.resource):
        raise ServiceError(
            404, "resource_not_found", "The requested resource was not found."
        )
    now = utc_now()
    value = ReviewAnnotation(
        review_id=review.id,
        clinician_user_id=actor.user_id,
        resource_type=body.resource.resource_type,
        resource_id=body.resource.resource_id,
        kind=body.kind,
        body=body.body,
        created_at=now,
        retention_expires_at=now + LONG_RECORD_RETENTION,
    )
    session.add(value)
    await session.flush()
    append_access_event(
        session,
        patient_user_id=review.patient_user_id,
        actor_user_id=actor.user_id,
        actor_type=AccessActorType.CLINICIAN,
        event_type=AccessEventType.ANNOTATION_CREATED,
        resource_type=body.resource.resource_type.value,
        resource_id=body.resource.resource_id,
        grant_id=grant.id,
        review_id=review.id,
        request_id=request.state.request_id,
        details={"kind": body.kind.value},
    )
    from ..collaboration_common import annotation_response

    response = annotation_response(value)
    return await commit_idempotent(
        session,
        user_id=actor.user_id,
        scope=scope,
        key=key,
        digest=digest,
        response=response,
        response_status=201,
    )


@router.get("/access-history", response_model=AccessHistoryResponse)
async def get_access_history(
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
    cursor: Annotated[str | None, Query(min_length=1, max_length=36)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> AccessHistoryResponse:
    statement = select(AccessEvent).where(AccessEvent.patient_user_id == actor.user_id)
    if cursor:
        cursor_value = await session.get(AccessEvent, cursor)
        if cursor_value is None or cursor_value.patient_user_id != actor.user_id:
            raise ServiceError(400, "invalid_cursor", "The history cursor is invalid.")
        statement = statement.where(
            or_(
                AccessEvent.created_at < cursor_value.created_at,
                (AccessEvent.created_at == cursor_value.created_at)
                & (AccessEvent.id < cursor_value.id),
            )
        )
    rows = list(
        await session.scalars(
            statement.order_by(
                AccessEvent.created_at.desc(), AccessEvent.id.desc()
            ).limit(limit + 1)
        )
    )
    page = rows[:limit]
    return AccessHistoryResponse(
        items=[history_item(value) for value in page],
        next_cursor=page[-1].id if len(rows) > limit else None,
    )

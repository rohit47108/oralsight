"""Shared privacy and response helpers for clinician collaboration and sharing."""

from __future__ import annotations

import base64
import hashlib
import hmac
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .collaboration_schemas import (
    AccessGrantResponse,
    AccessHistoryItem,
    AdminReviewEvidence,
    ClinicianIdentityRoleResponse,
    ClinicianReviewResponse,
    ClinicianVerificationResponse,
    ResourceRef,
    ResourceViewResponse,
    ReviewAnnotationResponse,
    ShareLinkResponse,
)
from .config import Settings
from .errors import ServiceError
from .models import (
    AccessActorType,
    AccessEvent,
    AccessEventType,
    AccessGrantResource,
    AccessGrantStatus,
    AnalysisRun,
    AuditEvent,
    ClinicianAccessGrant,
    ClinicianReview,
    ClinicianVerification,
    ClinicianVerificationStatus,
    LesionRecord,
    ReportArtifact,
    ReviewAnnotation,
    ScanSession,
    ShareLink,
    ShareLinkResource,
    ShareLinkStatus,
    ShareResourceType,
    UserRole,
    utc_now,
)
from .routes.analysis import analysis_response
from .routes.artifacts import _report_response
from .routes.capture import _scan_response
from .routes.tracking import lesion_response

LONG_RECORD_RETENTION = timedelta(days=365 * 7)
GRANT_DEFAULT_LIFETIME = timedelta(days=30)
GRANT_MAX_LIFETIME = timedelta(days=365)
SHARE_MAX_LIFETIME = timedelta(days=7)
SHARE_DEFAULT_LIFETIME = timedelta(hours=24)
SHARE_TOKEN_LIFETIME = timedelta(minutes=15)
SHARE_RECORD_RETENTION = timedelta(days=90)


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def is_future(value: datetime, *, now: datetime | None = None) -> bool:
    return as_utc(value) > (now or utc_now())


def keyed_digest(settings: Settings, namespace: str, value: str) -> str:
    key = settings.share_secret_derivation_key.get_secret_value().encode("utf-8")
    return hmac.new(
        key,
        f"oralsight:{namespace}:v1:{value}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def derive_urlsafe_secret(settings: Settings, namespace: str, value: str) -> str:
    digest = bytes.fromhex(keyed_digest(settings, namespace, value))
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def secret_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def secret_matches(value: str, expected_hash: str) -> bool:
    return hmac.compare_digest(secret_hash(value), expected_hash)


async def require_owned_resource(
    session: AsyncSession,
    *,
    patient_user_id: str,
    resource: ResourceRef,
):
    model = {
        ShareResourceType.SCAN_SESSION: ScanSession,
        ShareResourceType.REPORT: ReportArtifact,
        ShareResourceType.LESION: LesionRecord,
        ShareResourceType.ANALYSIS_RUN: AnalysisRun,
    }[resource.resource_type]
    value = await session.get(model, resource.resource_id)
    if (
        value is None
        or value.user_id != patient_user_id
        or getattr(value, "deleted_at", None) is not None
    ):
        raise ServiceError(
            404, "resource_not_found", "The requested resource was not found."
        )
    return value


async def resource_view_response(
    session: AsyncSession,
    *,
    patient_user_id: str,
    resource: ResourceRef,
) -> ResourceViewResponse:
    value = await require_owned_resource(
        session, patient_user_id=patient_user_id, resource=resource
    )
    if resource.resource_type is ShareResourceType.SCAN_SESSION:
        response = _scan_response(value)
    elif resource.resource_type is ShareResourceType.REPORT:
        response = _report_response(value)
    elif resource.resource_type is ShareResourceType.LESION:
        response = await lesion_response(session, value)
    else:
        response = await analysis_response(session, value)
    return ResourceViewResponse(
        resource_type=resource.resource_type,
        resource_id=resource.resource_id,
        data=response.model_dump(mode="json", by_alias=True),
    )


def append_audit_event(
    session: AsyncSession,
    *,
    patient_user_id: str,
    actor_user_id: str | None,
    event_type: str,
    resource_type: str,
    resource_id: str | None,
    request_id: str,
    details: dict[str, Any] | None = None,
) -> None:
    now = utc_now()
    session.add(
        AuditEvent(
            user_id=patient_user_id,
            actor_user_id=actor_user_id,
            event_type=event_type,
            resource_type=resource_type,
            resource_id=resource_id,
            request_id=request_id,
            details=details or {},
            retention_expires_at=now + LONG_RECORD_RETENTION,
        )
    )


def append_access_event(
    session: AsyncSession,
    *,
    patient_user_id: str,
    actor_user_id: str | None,
    actor_type: AccessActorType,
    event_type: AccessEventType,
    resource_type: str,
    resource_id: str | None,
    request_id: str,
    grant_id: str | None = None,
    share_id: str | None = None,
    review_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    now = utc_now()
    safe_details = details or {}
    session.add_all(
        [
            AccessEvent(
                patient_user_id=patient_user_id,
                actor_user_id=actor_user_id,
                actor_type=actor_type,
                event_type=event_type,
                resource_type=resource_type,
                resource_id=resource_id,
                grant_id=grant_id,
                share_id=share_id,
                review_id=review_id,
                request_id=request_id,
                details=safe_details,
                retention_expires_at=now + LONG_RECORD_RETENTION,
            ),
            AuditEvent(
                user_id=patient_user_id,
                actor_user_id=actor_user_id,
                event_type=f"access.{event_type.value}",
                resource_type=resource_type,
                resource_id=resource_id,
                request_id=request_id,
                details=safe_details,
                retention_expires_at=now + LONG_RECORD_RETENTION,
            ),
        ]
    )


def verification_response(
    value: ClinicianVerification,
    *,
    required_claim: str,
    applicant_role: UserRole | None = None,
    applicant_token_roles: frozenset[str] = frozenset(),
) -> ClinicianVerificationResponse:
    evidence = (
        AdminReviewEvidence.model_validate(value.reviewer_evidence)
        if value.reviewer_evidence
        else None
    )
    if value.status is not ClinicianVerificationStatus.VERIFIED:
        observation_status = "not_applicable"
    elif value.oidc_role_observed_at is None:
        observation_status = "awaiting_token_observation"
    else:
        observation_status = "observed"
    return ClinicianVerificationResponse(
        verification_id=value.id,
        applicant_user_id=value.user_id,
        status=value.status,
        profession=value.profession,
        license_jurisdiction=value.license_jurisdiction,
        license_number_suffix=value.license_number_suffix,
        organization=value.organization,
        applicant_evidence_ref=value.applicant_evidence_ref,
        submitted_at=value.submitted_at,
        reviewer_user_id=value.reviewer_user_id,
        reviewer_evidence=evidence,
        decision_reason=value.decision_reason,
        reviewed_at=value.reviewed_at,
        retention_expires_at=value.retention_expires_at,
        identity_role=ClinicianIdentityRoleResponse(
            required_claim=required_claim,
            observation_status=observation_status,
            oidc_role_observed_at=value.oidc_role_observed_at,
            privileged_access_ready=(
                applicant_role is UserRole.CLINICIAN
                and UserRole.CLINICIAN.value in applicant_token_roles
            ),
        ),
    )


async def grant_resources(session: AsyncSession, grant_id: str) -> list[ResourceRef]:
    rows = list(
        await session.scalars(
            select(AccessGrantResource)
            .where(AccessGrantResource.grant_id == grant_id)
            .order_by(AccessGrantResource.created_at, AccessGrantResource.id)
        )
    )
    return [
        ResourceRef(resource_type=value.resource_type, resource_id=value.resource_id)
        for value in rows
    ]


async def share_resources(session: AsyncSession, share_id: str) -> list[ResourceRef]:
    rows = list(
        await session.scalars(
            select(ShareLinkResource)
            .where(ShareLinkResource.share_id == share_id)
            .order_by(ShareLinkResource.created_at, ShareLinkResource.id)
        )
    )
    return [
        ResourceRef(resource_type=value.resource_type, resource_id=value.resource_id)
        for value in rows
    ]


async def grant_response(
    session: AsyncSession, value: ClinicianAccessGrant
) -> AccessGrantResponse:
    review = await session.scalar(
        select(ClinicianReview).where(ClinicianReview.grant_id == value.id)
    )
    if review is None:
        raise ServiceError(
            500, "invalid_grant_state", "The access grant is incomplete."
        )
    now = utc_now()
    active = (
        value.status is AccessGrantStatus.ACTIVE
        and value.revoked_at is None
        and is_future(value.expires_at, now=now)
    )
    return AccessGrantResponse(
        grant_id=value.id,
        patient_user_id=value.patient_user_id,
        clinician_user_id=value.clinician_user_id,
        status=value.status,
        label=value.label,
        resources=await grant_resources(session, value.id),
        review_id=review.id,
        expires_at=value.expires_at,
        revoked_at=value.revoked_at,
        created_at=value.created_at,
        updated_at=value.updated_at,
        retention_expires_at=value.retention_expires_at,
        active=active,
    )


async def share_response(session: AsyncSession, value: ShareLink) -> ShareLinkResponse:
    now = utc_now()
    active = (
        value.status is ShareLinkStatus.ACTIVE
        and value.revoked_at is None
        and is_future(value.expires_at, now=now)
        and value.exchange_count < value.max_exchanges
    )
    return ShareLinkResponse(
        share_id=value.id,
        patient_user_id=value.patient_user_id,
        status=value.status,
        resources=await share_resources(session, value.id),
        expires_at=value.expires_at,
        max_exchanges=value.max_exchanges,
        exchange_count=value.exchange_count,
        revoked_at=value.revoked_at,
        created_at=value.created_at,
        retention_expires_at=value.retention_expires_at,
        active=active,
    )


def annotation_response(value: ReviewAnnotation) -> ReviewAnnotationResponse:
    return ReviewAnnotationResponse(
        annotation_id=value.id,
        review_id=value.review_id,
        clinician_user_id=value.clinician_user_id,
        resource=ResourceRef(
            resource_type=value.resource_type, resource_id=value.resource_id
        ),
        kind=value.kind,
        body=value.body,
        created_at=value.created_at,
        retention_expires_at=value.retention_expires_at,
    )


async def review_response(
    session: AsyncSession, value: ClinicianReview
) -> ClinicianReviewResponse:
    grant = await session.get(ClinicianAccessGrant, value.grant_id)
    if grant is None:
        raise ServiceError(500, "invalid_review_state", "The review is incomplete.")
    annotations = list(
        await session.scalars(
            select(ReviewAnnotation)
            .where(ReviewAnnotation.review_id == value.id)
            .order_by(ReviewAnnotation.created_at, ReviewAnnotation.id)
        )
    )
    now = utc_now()
    access_active = (
        grant.status is AccessGrantStatus.ACTIVE
        and grant.revoked_at is None
        and is_future(grant.expires_at, now=now)
    )
    return ClinicianReviewResponse(
        review_id=value.id,
        grant_id=value.grant_id,
        patient_user_id=value.patient_user_id,
        clinician_user_id=value.clinician_user_id,
        status=value.status,
        summary=value.summary,
        resources=await grant_resources(session, value.grant_id),
        annotations=[annotation_response(item) for item in annotations],
        grant_expires_at=grant.expires_at,
        grant_revoked_at=grant.revoked_at,
        created_at=value.created_at,
        updated_at=value.updated_at,
        started_at=value.started_at,
        completed_at=value.completed_at,
        retention_expires_at=value.retention_expires_at,
        access_active=access_active,
    )


def history_item(value: AccessEvent) -> AccessHistoryItem:
    return AccessHistoryItem(
        event_id=value.id,
        actor_user_id=value.actor_user_id,
        actor_type=value.actor_type,
        event_type=value.event_type,
        resource_type=value.resource_type,
        resource_id=value.resource_id,
        grant_id=value.grant_id,
        share_id=value.share_id,
        review_id=value.review_id,
        details=value.details,
        created_at=value.created_at,
        retention_expires_at=value.retention_expires_at,
    )
    (ClinicianIdentityRoleResponse,)

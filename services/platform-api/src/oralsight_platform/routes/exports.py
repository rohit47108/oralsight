"""Recipient-key-encrypted portable account exports and owner downloads."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import Response
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..dependencies import Actor, get_current_actor, get_session
from ..errors import ServiceError
from ..collaboration_common import as_utc
from ..internal_schemas import (
    DataExportArtifactList,
    DataExportArtifactResponse,
    ExportEncryptionResponse,
    ExportRenderRequest,
    ExportRenderResponse,
)
from ..models import (
    AccessGrantResource,
    AccessEvent,
    AnalysisRun,
    AnalyticsEvent,
    AuditEvent,
    CandidateObservation,
    CaptureAsset,
    CaptureSet,
    CaptureStatus,
    CaptureView,
    ClinicianAccessGrant,
    ClinicianReview,
    ClinicianVerification,
    ConsentRecord,
    DataExportArtifact,
    Device,
    EntityTombstone,
    GeneratedArtifact,
    Job,
    JobType,
    LesionObservationLink,
    LesionRecord,
    MatchDecision,
    MatchProposal,
    ReportArtifact,
    ReviewAnnotation,
    ScanSession,
    ShareLink,
    ShareLinkResource,
    SyncChange,
    SyncEntityState,
    User,
    new_id,
    utc_now,
)
from ..object_storage import StorageError, StorageNotFound
from ..portable_export import ExportFile, build_portable_zip, encrypt_portable_zip
from .internal_assets import _authenticate_worker

router = APIRouter(tags=["portable exports"])
MAX_EXPORT_REQUEST_BYTES = 32_768


def _artifact_response(value: DataExportArtifact) -> DataExportArtifactResponse:
    return DataExportArtifactResponse(
        artifact_id=value.id,
        export_request_id=value.export_request_id,
        job_id=value.job_id,
        sha256=value.content_sha256,
        byte_size=value.byte_size,
        included_files=value.included_files,
        encryption=ExportEncryptionResponse.model_validate(value.encryption_metadata),
        created_at=value.created_at,
        retention_expires_at=value.retention_expires_at,
    )


def _record(value, fields: tuple[str, ...]) -> dict[str, Any]:
    return {field: getattr(value, field) for field in fields}


async def _owned_rows(session: AsyncSession, model, user_id: str):
    return list(await session.scalars(select(model).where(model.user_id == user_id)))


async def _portable_records(session: AsyncSession, user: User) -> dict[str, Any]:
    devices = await _owned_rows(session, Device, user.id)
    consents = await _owned_rows(session, ConsentRecord, user.id)
    scans = await _owned_rows(session, ScanSession, user.id)
    assets = await _owned_rows(session, CaptureAsset, user.id)
    capture_sets = await _owned_rows(session, CaptureSet, user.id)
    views = await _owned_rows(session, CaptureView, user.id)
    analyses = await _owned_rows(session, AnalysisRun, user.id)
    observations = await _owned_rows(session, CandidateObservation, user.id)
    proposals = await _owned_rows(session, MatchProposal, user.id)
    decisions = await _owned_rows(session, MatchDecision, user.id)
    lesions = await _owned_rows(session, LesionRecord, user.id)
    lesion_links = await _owned_rows(session, LesionObservationLink, user.id)
    reports = await _owned_rows(session, ReportArtifact, user.id)
    generated_artifacts = await _owned_rows(session, GeneratedArtifact, user.id)
    jobs = await _owned_rows(session, Job, user.id)
    export_artifacts = await _owned_rows(session, DataExportArtifact, user.id)
    clinician_verifications = await _owned_rows(session, ClinicianVerification, user.id)
    sync_states = await _owned_rows(session, SyncEntityState, user.id)
    tombstones = await _owned_rows(session, EntityTombstone, user.id)
    sync_changes = await _owned_rows(session, SyncChange, user.id)
    analytics = await _owned_rows(session, AnalyticsEvent, user.id)
    audit = await _owned_rows(session, AuditEvent, user.id)
    access = list(
        await session.scalars(
            select(AccessEvent).where(AccessEvent.patient_user_id == user.id)
        )
    )
    grants = list(
        await session.scalars(
            select(ClinicianAccessGrant).where(
                ClinicianAccessGrant.patient_user_id == user.id
            )
        )
    )
    shares = list(
        await session.scalars(
            select(ShareLink).where(ShareLink.patient_user_id == user.id)
        )
    )
    reviews = list(
        await session.scalars(
            select(ClinicianReview).where(ClinicianReview.patient_user_id == user.id)
        )
    )
    grant_ids = [value.id for value in grants]
    share_ids = [value.id for value in shares]
    review_ids = [value.id for value in reviews]
    grant_resources = (
        list(
            await session.scalars(
                select(AccessGrantResource).where(
                    AccessGrantResource.grant_id.in_(grant_ids)
                )
            )
        )
        if grant_ids
        else []
    )
    share_resources = (
        list(
            await session.scalars(
                select(ShareLinkResource).where(
                    ShareLinkResource.share_id.in_(share_ids)
                )
            )
        )
        if share_ids
        else []
    )
    annotations = (
        list(
            await session.scalars(
                select(ReviewAnnotation).where(
                    ReviewAnnotation.review_id.in_(review_ids)
                )
            )
        )
        if review_ids
        else []
    )
    return {
        "account": {
            "id": user.id,
            "role": user.role,
            "status": user.status,
            "createdAt": user.created_at,
            "analyticsEnabled": user.analytics_enabled,
            "analyticsPolicyVersion": user.analytics_policy_version,
            "analyticsUpdatedAt": user.analytics_updated_at,
        },
        "devices": [
            _record(
                value, ("id", "platform", "display_name", "created_at", "revoked_at")
            )
            for value in devices
        ],
        "consents": [
            _record(
                value,
                (
                    "id",
                    "document_id",
                    "document_version",
                    "document_sha256",
                    "device_id",
                    "accepted",
                    "accepted_at",
                    "revoked_at",
                ),
            )
            for value in consents
        ],
        "scans": [
            _record(
                value,
                (
                    "id",
                    "device_id",
                    "consent_record_id",
                    "protocol",
                    "status",
                    "created_at",
                    "completed_at",
                    "deleted_at",
                ),
            )
            for value in scans
        ],
        "captureAssets": [
            _record(
                value,
                (
                    "id",
                    "scan_session_id",
                    "region",
                    "capture_angle",
                    "sequence_number",
                    "media_kind",
                    "media_type",
                    "content_sha256",
                    "byte_size",
                    "status",
                    "width_px",
                    "height_px",
                    "duration_ms",
                    "input_origin",
                    "created_at",
                    "retention_expires_at",
                    "deleted_at",
                ),
            )
            for value in assets
        ],
        "captureSets": [
            _record(
                value,
                (
                    "id",
                    "scan_session_id",
                    "region",
                    "protocol",
                    "primary_view_id",
                    "complete",
                    "version",
                    "created_at",
                    "updated_at",
                ),
            )
            for value in capture_sets
        ],
        "captureViews": [
            _record(
                value,
                (
                    "id",
                    "capture_set_id",
                    "asset_id",
                    "region",
                    "anatomical_site",
                    "angle",
                    "source_video_asset_id",
                    "quality_accepted",
                    "quality_reasons",
                    "ordinal",
                    "captured_at",
                ),
            )
            for value in views
        ],
        "analysisRuns": [
            _record(
                value,
                (
                    "id",
                    "capture_set_id",
                    "requested_heads",
                    "status",
                    "input_origin",
                    "analysis_origin",
                    "source_asset_sha256",
                    "model_versions",
                    "artifact_hashes",
                    "abstention_reasons",
                    "started_at",
                    "completed_at",
                    "persisted",
                    "signed_envelope_id",
                    "worker_job_id",
                    "created_at",
                    "deleted_at",
                ),
            )
            for value in analyses
        ],
        "observations": [
            _record(
                value,
                (
                    "id",
                    "analysis_run_id",
                    "capture_view_id",
                    "region",
                    "anatomical_site",
                    "candidate_mask",
                    "descriptors",
                    "uncertainty",
                    "appearance_output",
                    "disease_research_output",
                    "calibration_status",
                    "calibration_evidence",
                    "calibration_evidence_sha256",
                    "estimated_width_mm",
                    "estimated_height_mm",
                    "estimated_area_mm2",
                    "named_mesh",
                    "uv_u",
                    "uv_v",
                    "asset_version",
                    "limitations",
                    "created_at",
                ),
            )
            for value in observations
        ],
        "matchProposals": [
            _record(
                value,
                (
                    "id",
                    "current_observation_id",
                    "candidate_prior_observation_id",
                    "candidate_lesion_id",
                    "proposal_origin",
                    "score",
                    "rank",
                    "model_versions",
                    "generated_at",
                    "expires_at",
                ),
            )
            for value in proposals
        ],
        "matchDecisions": [
            _record(
                value,
                (
                    "id",
                    "proposal_id",
                    "decision",
                    "rationale",
                    "sequence",
                    "lesion_id",
                    "decided_at",
                ),
            )
            for value in decisions
        ],
        "lesions": [
            _record(
                value,
                (
                    "id",
                    "region",
                    "anatomical_site",
                    "label",
                    "status",
                    "version",
                    "created_at",
                    "updated_at",
                ),
            )
            for value in lesions
        ],
        "lesionObservationLinks": [
            _record(
                value, ("id", "lesion_id", "observation_id", "decision_id", "linked_at")
            )
            for value in lesion_links
        ],
        "reports": [
            _record(
                value,
                (
                    "id",
                    "scan_session_ids",
                    "report_format",
                    "asset_id",
                    "media_type",
                    "content_sha256",
                    "byte_size",
                    "locale",
                    "accessible",
                    "input_origins",
                    "analysis_origins",
                    "model_versions",
                    "signed_envelope_id",
                    "created_at",
                    "retention_expires_at",
                    "deleted_at",
                ),
            )
            for value in reports
        ],
        "generatedArtifacts": [
            _record(
                value,
                (
                    "id",
                    "purpose",
                    "media_type",
                    "content_sha256",
                    "size_bytes",
                    "provenance",
                    "created_at",
                    "retention_expires_at",
                ),
            )
            for value in generated_artifacts
        ],
        "jobs": [
            _record(
                value,
                (
                    "id",
                    "job_type",
                    "status",
                    "input_refs",
                    "output_refs",
                    "progress_percent",
                    "attempt_count",
                    "max_attempts",
                    "error_code",
                    "error_message",
                    "request_payload",
                    "result_outcome",
                    "result_payload",
                    "reason_code",
                    "created_at",
                    "started_at",
                    "completed_at",
                    "expires_at",
                ),
            )
            for value in jobs
        ],
        "priorExportArtifacts": [
            _record(
                value,
                (
                    "id",
                    "job_id",
                    "export_request_id",
                    "content_sha256",
                    "byte_size",
                    "included_files",
                    "encryption_metadata",
                    "created_at",
                    "retention_expires_at",
                ),
            )
            for value in export_artifacts
        ],
        "syncState": [
            _record(
                value,
                (
                    "entity_type",
                    "entity_id",
                    "version",
                    "encrypted_payload",
                    "last_server_sequence",
                    "updated_at",
                ),
            )
            for value in sync_states
        ],
        "syncTombstones": [
            _record(
                value,
                (
                    "entity_type",
                    "entity_id",
                    "deleted_version",
                    "server_sequence",
                    "deleted_at",
                ),
            )
            for value in tombstones
        ],
        "syncChanges": [
            _record(
                value,
                (
                    "operation_id",
                    "device_id",
                    "entity_type",
                    "entity_id",
                    "entity_version",
                    "operation",
                    "encrypted_payload",
                    "tombstone",
                    "apply_status",
                    "applied",
                    "server_sequence",
                    "occurred_at",
                    "accepted_at",
                ),
            )
            for value in sync_changes
        ],
        "analyticsEvents": [
            _record(
                value,
                (
                    "event_name",
                    "platform",
                    "app_version",
                    "surface",
                    "outcome",
                    "received_at",
                ),
            )
            for value in analytics
        ],
        "accessHistory": [
            _record(
                value,
                (
                    "actor_type",
                    "actor_user_id",
                    "event_type",
                    "resource_type",
                    "resource_id",
                    "grant_id",
                    "share_id",
                    "review_id",
                    "details",
                    "created_at",
                ),
            )
            for value in access
        ],
        "auditHistory": [
            _record(
                value,
                (
                    "actor_user_id",
                    "event_type",
                    "resource_type",
                    "resource_id",
                    "details",
                    "created_at",
                ),
            )
            for value in audit
        ],
        "clinicianGrants": [
            _record(
                value,
                (
                    "id",
                    "clinician_user_id",
                    "status",
                    "label",
                    "expires_at",
                    "revoked_at",
                    "created_at",
                ),
            )
            for value in grants
        ],
        "clinicianGrantResources": [
            _record(value, ("grant_id", "resource_type", "resource_id"))
            for value in grant_resources
        ],
        "clinicianReviews": [
            _record(
                value,
                (
                    "id",
                    "grant_id",
                    "clinician_user_id",
                    "status",
                    "summary",
                    "created_at",
                    "started_at",
                    "completed_at",
                ),
            )
            for value in reviews
        ],
        "clinicianAnnotations": [
            _record(
                value,
                (
                    "id",
                    "review_id",
                    "clinician_user_id",
                    "resource_type",
                    "resource_id",
                    "kind",
                    "body",
                    "created_at",
                ),
            )
            for value in annotations
        ],
        "clinicianVerifications": [
            _record(
                value,
                (
                    "id",
                    "status",
                    "profession",
                    "license_jurisdiction",
                    "license_number_suffix",
                    "organization",
                    "applicant_evidence_ref",
                    "submitted_at",
                    "reviewer_evidence",
                    "decision_reason",
                    "reviewed_at",
                ),
            )
            for value in clinician_verifications
        ],
        "shares": [
            _record(
                value,
                (
                    "id",
                    "status",
                    "expires_at",
                    "max_exchanges",
                    "exchange_count",
                    "revoked_at",
                    "created_at",
                ),
            )
            for value in shares
        ],
        "shareResources": [
            _record(value, ("share_id", "resource_type", "resource_id"))
            for value in share_resources
        ],
    }


def _file_extension(media_type: str) -> str:
    return {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "video/mp4": ".mp4",
        "application/pdf": ".pdf",
        "model/gltf-binary": ".glb",
    }.get(media_type, ".bin")


async def _export_files(request: Request, session: AsyncSession, user_id: str):
    files: list[ExportFile] = []
    skipped: list[dict[str, str]] = []
    total = 0
    candidates: list[tuple[str, str, str, int, str]] = []
    for value in await _owned_rows(session, CaptureAsset, user_id):
        if value.status is CaptureStatus.AVAILABLE and value.deleted_at is None:
            candidates.append(
                (
                    f"files/captures/{value.id}{_file_extension(value.media_type)}",
                    value.object_key,
                    value.media_type,
                    value.byte_size,
                    value.content_sha256,
                )
            )
    for value in await _owned_rows(session, ReportArtifact, user_id):
        if value.object_key and value.deleted_at is None:
            candidates.append(
                (
                    f"files/reports/{value.id}{_file_extension(value.media_type)}",
                    value.object_key,
                    value.media_type,
                    value.byte_size,
                    value.content_sha256,
                )
            )
    for value in await _owned_rows(session, GeneratedArtifact, user_id):
        candidates.append(
            (
                f"files/generated/{value.id}{_file_extension(value.media_type)}",
                value.object_key,
                value.media_type,
                value.size_bytes,
                value.content_sha256,
            )
        )
    for path, object_key, media_type, size, sha256 in candidates:
        if total + size > request.app.state.settings.export_plaintext_max_bytes:
            skipped.append({"path": path, "reason": "export_size_limit"})
            continue
        try:
            data = await request.app.state.object_storage.get_bytes(
                object_key, max_bytes=size
            )
        except StorageNotFound:
            skipped.append({"path": path, "reason": "content_unavailable"})
            continue
        except StorageError as exc:
            raise ServiceError(
                503, "object_storage_unavailable", "Storage is unavailable."
            ) from exc
        if len(data) != size or hashlib.sha256(data).hexdigest() != sha256:
            skipped.append({"path": path, "reason": "integrity_check_failed"})
            continue
        files.append(
            ExportFile(
                path=path,
                data=bytearray(data),
                media_type=media_type,
                sha256=sha256,
            )
        )
        total += size
    return files, skipped


@router.post("/internal/v2/exports/render", response_model=ExportRenderResponse)
async def render_export(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    service_id: Annotated[str | None, Header(alias="X-OralSight-Service")] = None,
    timestamp: Annotated[str | None, Header(alias="X-OralSight-Timestamp")] = None,
    nonce: Annotated[str | None, Header(alias="X-OralSight-Nonce")] = None,
    content_sha256: Annotated[
        str | None, Header(alias="X-OralSight-Content-SHA256")
    ] = None,
    signature: Annotated[str | None, Header(alias="X-OralSight-Signature")] = None,
) -> ExportRenderResponse:
    raw = await request.body()
    if len(raw) > MAX_EXPORT_REQUEST_BYTES:
        raise ServiceError(413, "request_too_large", "The request is too large.")
    await _authenticate_worker(
        request=request,
        session=session,
        body=raw,
        service_id=service_id,
        timestamp=timestamp,
        nonce=nonce,
        content_sha256=content_sha256,
        signature=signature,
    )
    try:
        body = ExportRenderRequest.model_validate_json(raw)
    except ValidationError as exc:
        raise ServiceError(
            422, "invalid_worker_payload", "The worker payload is invalid."
        ) from exc
    job = await session.get(Job, body.job_id)
    if job is None or job.job_type is not JobType.DATA_EXPORT:
        raise ServiceError(404, "job_not_found", "The export job was not found.")
    expected = {
        key: value for key, value in job.request_payload.items() if key != "kind"
    }
    submitted = body.model_dump(mode="json", by_alias=True, exclude={"job_id"})
    if submitted != expected:
        raise ServiceError(
            422, "export_job_mismatch", "The export request does not match its job."
        )
    existing = await session.scalar(
        select(DataExportArtifact).where(DataExportArtifact.job_id == job.id)
    )
    if existing is not None:
        response = _artifact_response(existing)
        return ExportRenderResponse(
            export_request_id=response.export_request_id,
            status="complete",
            artifact_id=response.artifact_id,
            media_type=response.media_type,
            sha256=response.sha256,
            byte_size=response.byte_size,
            encryption=response.encryption,
        )
    user = await session.get(User, job.user_id)
    if user is None:
        raise ServiceError(404, "account_not_found", "The account was not found.")
    records = await _portable_records(session, user)
    files: list[ExportFile] = []
    skipped: list[dict[str, str]] = []
    if body.include_files:
        files, skipped = await _export_files(request, session, user.id)
    plaintext = build_portable_zip(
        export_request_id=body.export_request_id,
        generated_at=utc_now(),
        records=records,
        files=files,
        skipped_files=skipped,
    )
    if len(plaintext) > request.app.state.settings.export_plaintext_max_bytes:
        plaintext[:] = b"\x00" * len(plaintext)
        raise ServiceError(413, "export_too_large", "The portable export is too large.")
    encrypted = encrypt_portable_zip(
        plaintext,
        recipient_public_key_b64=body.encryption.recipient_public_key_b64,
    )
    if (
        len(encrypted.ciphertext)
        > request.app.state.settings.export_encrypted_max_bytes
    ):
        raise ServiceError(413, "export_too_large", "The portable export is too large.")
    artifact_id = new_id()
    object_key = f"users/{user.id}/exports/{artifact_id}.oralsight-export"
    try:
        await request.app.state.object_storage.put_bytes(
            object_key,
            encrypted.ciphertext,
            media_type="application/vnd.oralsight.export",
            sha256=encrypted.sha256,
        )
    except StorageError as exc:
        raise ServiceError(
            503, "object_storage_unavailable", "Storage is unavailable."
        ) from exc
    now = utc_now()
    value = DataExportArtifact(
        id=artifact_id,
        user_id=user.id,
        job_id=job.id,
        export_request_id=body.export_request_id,
        object_key=object_key,
        content_sha256=encrypted.sha256,
        byte_size=len(encrypted.ciphertext),
        included_files=body.include_files,
        encryption_metadata=encrypted.encryption,
        created_at=now,
        retention_expires_at=now
        + timedelta(days=request.app.state.settings.export_retention_days),
    )
    session.add(value)
    job.resource_id = value.id
    job.output_refs = [*job.output_refs, value.id]
    try:
        await session.commit()
    except Exception:
        await session.rollback()
        try:
            await request.app.state.object_storage.delete(object_key)
        except StorageError:
            pass
        raise
    return ExportRenderResponse(
        export_request_id=value.export_request_id,
        status="complete",
        artifact_id=value.id,
        media_type="application/vnd.oralsight.export",
        sha256=value.content_sha256,
        byte_size=value.byte_size,
        encryption=ExportEncryptionResponse.model_validate(value.encryption_metadata),
    )


async def _owned_export(
    session: AsyncSession, artifact_id: str, actor: Actor
) -> DataExportArtifact:
    value = await session.get(DataExportArtifact, artifact_id)
    if value is None or value.user_id != actor.user_id:
        raise ServiceError(
            404, "resource_not_found", "The requested resource was not found."
        )
    if as_utc(value.retention_expires_at) <= utc_now():
        raise ServiceError(410, "export_expired", "The export has expired.")
    return value


@router.get("/v2/data-exports", response_model=DataExportArtifactList)
async def list_exports(
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=50)] = 25,
    before: Annotated[datetime | None, Query()] = None,
) -> DataExportArtifactList:
    query = select(DataExportArtifact).where(
        DataExportArtifact.user_id == actor.user_id,
        DataExportArtifact.retention_expires_at > utc_now(),
    )
    if before is not None:
        query = query.where(DataExportArtifact.created_at < before)
    rows = list(
        await session.scalars(
            query.order_by(
                DataExportArtifact.created_at.desc(), DataExportArtifact.id.desc()
            ).limit(limit + 1)
        )
    )
    has_more = len(rows) > limit
    rows = rows[:limit]
    cursor = (
        rows[-1].created_at.astimezone(UTC).isoformat() if has_more and rows else None
    )
    return DataExportArtifactList(
        items=[_artifact_response(value) for value in rows], next_cursor=cursor
    )


@router.get("/v2/data-exports/{artifact_id}", response_model=DataExportArtifactResponse)
async def get_export(
    artifact_id: str,
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DataExportArtifactResponse:
    return _artifact_response(await _owned_export(session, artifact_id, actor))


@router.get("/v2/data-exports/{artifact_id}/content")
async def get_export_content(
    artifact_id: str,
    request: Request,
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    value = await _owned_export(session, artifact_id, actor)
    try:
        data = await request.app.state.object_storage.get_bytes(
            value.object_key, max_bytes=value.byte_size
        )
    except StorageNotFound as exc:
        raise ServiceError(
            410, "export_content_unavailable", "The export is unavailable."
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
            500, "stored_export_corrupt", "The stored export failed verification."
        )
    return Response(
        content=data,
        media_type="application/vnd.oralsight.export",
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": f'attachment; filename="oralsight-export-{value.export_request_id}.bin"',
        },
    )

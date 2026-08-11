"""Validate owner-scoped job inputs, build worker envelopes, and publish outbox rows."""

from __future__ import annotations

import json
from datetime import timedelta
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .errors import ServiceError
from .job_contracts import (
    AnalyzePayload,
    AssetPointer,
    ComparePayload,
    DataExportPayload,
    JobEnvelope,
    ReconstructionPayload,
    ReportPayload,
    SummaryVideoPayload,
    validate_job_payload,
)
from .job_queue import QueueUnavailable
from .models import (
    CandidateObservation,
    CalibrationStatus,
    CaptureAsset,
    CaptureSet,
    CaptureStatus,
    CaptureView,
    ConsentRecord,
    Job,
    JobType,
    LesionObservationLink,
    MatchDecision,
    ReportArtifact,
    ScanSession,
    utc_now,
)
from .product_consent import DOCUMENT_ID, DOCUMENT_SHA256, DOCUMENT_VERSION


async def _owned(session: AsyncSession, model, resource_id: str, user_id: str):
    value = await session.get(model, resource_id)
    if (
        value is None
        or getattr(value, "user_id", None) != user_id
        or getattr(value, "deleted_at", None) is not None
    ):
        raise ServiceError(
            404, "resource_not_found", "The requested resource was not found."
        )
    return value


async def _asset(
    session: AsyncSession, pointer: AssetPointer, user_id: str
) -> CaptureAsset:
    value = await _owned(session, CaptureAsset, str(pointer.asset_id), user_id)
    if value.status is not CaptureStatus.AVAILABLE:
        raise ServiceError(409, "asset_not_available", "The asset is not available.")
    if (
        value.content_sha256 != pointer.sha256
        or value.media_type != pointer.media_type
        or value.byte_size != pointer.size_bytes
    ):
        raise ServiceError(
            422,
            "asset_pointer_mismatch",
            "The asset pointer does not match stored metadata.",
        )
    return value


async def _capture(
    session: AsyncSession,
    *,
    capture_id: UUID,
    pointer: AssetPointer,
    user_id: str,
    expected_region=None,
    capture_set_id: str | None = None,
) -> tuple[CaptureView, CaptureAsset]:
    view = await _owned(session, CaptureView, str(capture_id), user_id)
    asset = await _asset(session, pointer, user_id)
    if view.asset_id != asset.id:
        raise ServiceError(
            422, "capture_asset_mismatch", "The capture and asset do not match."
        )
    if expected_region is not None and view.region != expected_region:
        raise ServiceError(
            422, "capture_region_mismatch", "The capture region does not match."
        )
    if capture_set_id is not None and view.capture_set_id != capture_set_id:
        raise ServiceError(
            422,
            "capture_set_mismatch",
            "The capture does not belong to the requested set.",
        )
    return view, asset


async def validate_owned_job_payload(
    session: AsyncSession,
    *,
    user_id: str,
    job_type: JobType,
    raw_payload: dict,
) -> tuple[dict, list[str], list[str]]:
    if job_type in {JobType.ACCOUNT_DELETION, JobType.DELETE_ALL}:
        raise ServiceError(
            422, "unsupported_job_type", "This job type is not available."
        )
    try:
        payload = validate_job_payload(job_type, raw_payload)
    except (ValidationError, ValueError, TypeError) as exc:
        raise ServiceError(
            422, "invalid_job_payload", "The job payload is invalid."
        ) from exc
    refs: set[str] = set()
    asset_ids: set[str] = set()
    if isinstance(payload, AnalyzePayload):
        view, asset = await _capture(
            session,
            capture_id=payload.capture_id,
            pointer=payload.image,
            user_id=user_id,
            expected_region=payload.selected_region,
        )
        capture_set = await _owned(session, CaptureSet, view.capture_set_id, user_id)
        if not capture_set.complete:
            raise ServiceError(
                409,
                "capture_set_incomplete",
                "Analysis requires a complete capture set.",
            )
        refs.update({view.id, capture_set.id, asset.id})
        asset_ids.add(asset.id)
    elif isinstance(payload, ComparePayload):
        baseline_view, baseline_asset = await _capture(
            session,
            capture_id=payload.baseline_capture_id,
            pointer=payload.baseline_image,
            user_id=user_id,
            expected_region=payload.region,
        )
        current_view, current_asset = await _capture(
            session,
            capture_id=payload.current_capture_id,
            pointer=payload.current_image,
            user_id=user_id,
            expected_region=payload.region,
        )
        refs.update(
            {
                baseline_view.id,
                current_view.id,
                baseline_asset.id,
                current_asset.id,
            }
        )
        asset_ids.update({baseline_asset.id, current_asset.id})
    elif isinstance(payload, ReconstructionPayload):
        capture_set = await _owned(
            session, CaptureSet, str(payload.capture_set_id), user_id
        )
        refs.add(capture_set.id)
        for item in payload.views:
            view, asset = await _capture(
                session,
                capture_id=item.capture_id,
                pointer=item.image,
                user_id=user_id,
                expected_region=item.region,
                capture_set_id=capture_set.id,
            )
            refs.update({view.id, asset.id})
            asset_ids.add(asset.id)
        for pin in payload.pins:
            observation = await _owned(
                session, CandidateObservation, str(pin.observation_id), user_id
            )
            confirmed_link = await session.scalar(
                select(LesionObservationLink.id).where(
                    LesionObservationLink.user_id == user_id,
                    LesionObservationLink.observation_id == observation.id,
                )
            )
            if confirmed_link is None:
                raise ServiceError(
                    409,
                    "observation_not_user_confirmed",
                    "Only user-confirmed observations may be placed on the map.",
                )
            if (
                observation.region != pin.region
                or observation.named_mesh != pin.mesh_name
                or observation.asset_version != pin.asset_version
                or observation.uv_u is None
                or observation.uv_v is None
                or abs(observation.uv_u - pin.uv_coordinates[0]) > 1e-6
                or abs(observation.uv_v - pin.uv_coordinates[1]) > 1e-6
            ):
                raise ServiceError(
                    422,
                    "observation_pin_mismatch",
                    "The map pin does not match the stored observation mapping.",
                )
            if pin.estimated_area_mm2 is not None and (
                observation.calibration_status is not CalibrationStatus.VALID
                or observation.estimated_area_mm2 is None
                or abs(observation.estimated_area_mm2 - pin.estimated_area_mm2) > 1e-6
            ):
                raise ServiceError(
                    422,
                    "observation_calibration_mismatch",
                    "The map pin measurement lacks matching calibration evidence.",
                )
            refs.add(observation.id)
    elif isinstance(payload, ReportPayload):
        scan = await _owned(session, ScanSession, str(payload.scan_session_id), user_id)
        consent = await _owned(
            session, ConsentRecord, str(payload.consent_record_id), user_id
        )
        if (
            not consent.accepted
            or consent.revoked_at is not None
            or consent.document_id != DOCUMENT_ID
            or consent.document_version != DOCUMENT_VERSION
            or consent.document_sha256 != DOCUMENT_SHA256
            or (
                scan.consent_record_id is not None
                and scan.consent_record_id != consent.id
            )
        ):
            raise ServiceError(
                409,
                "active_product_consent_required",
                "The report requires the active consent used for this scan.",
            )
        refs.update({scan.id, consent.id})
        for observation_id in payload.observation_ids:
            observation = await _owned(
                session, CandidateObservation, str(observation_id), user_id
            )
            refs.add(observation.id)
        for comparison_id in payload.comparison_ids:
            comparison = await _owned(
                session, MatchDecision, str(comparison_id), user_id
            )
            refs.add(comparison.id)
    elif isinstance(payload, SummaryVideoPayload):
        scan = await _owned(session, ScanSession, str(payload.scan_session_id), user_id)
        report = await _owned(session, ReportArtifact, str(payload.report_id), user_id)
        if scan.id not in report.scan_session_ids:
            raise ServiceError(
                422, "report_scan_mismatch", "The report does not cover this scan."
            )
        refs.update({scan.id, report.id})
        for item in payload.selected_observations:
            observation = await _owned(
                session, CandidateObservation, str(item.observation_id), user_id
            )
            if (
                observation.capture_view_id != str(item.current_capture_id)
                or observation.region != item.region
            ):
                raise ServiceError(
                    422,
                    "summary_observation_mismatch",
                    "A summary observation does not match its capture.",
                )
            current_view, current_asset = await _capture(
                session,
                capture_id=item.current_capture_id,
                pointer=item.current_image,
                user_id=user_id,
                expected_region=item.region,
            )
            refs.update({observation.id, current_view.id, current_asset.id})
            asset_ids.add(current_asset.id)
            if item.baseline_capture_id and item.baseline_image:
                baseline_view, baseline_asset = await _capture(
                    session,
                    capture_id=item.baseline_capture_id,
                    pointer=item.baseline_image,
                    user_id=user_id,
                    expected_region=item.region,
                )
                refs.update({baseline_view.id, baseline_asset.id})
                asset_ids.add(baseline_asset.id)
    elif isinstance(payload, DataExportPayload):
        # The request UUID is newly minted by the caller and becomes the durable
        # export reference; no existing clinical resource is required.
        refs.add(str(payload.export_request_id))
    return (
        payload.model_dump(mode="json", by_alias=True),
        sorted(refs),
        sorted(asset_ids),
    )


def build_job_envelope(
    job: Job,
    *,
    request_id: str,
    asset_ids: list[str],
) -> JobEnvelope:
    now = job.created_at or utc_now()
    input_delete = now + timedelta(hours=24)
    success_delete = now + timedelta(days=30)
    failure_delete = now + timedelta(days=7)
    return JobEnvelope.model_validate(
        {
            "jobId": job.id,
            "requestId": request_id,
            "accountId": job.user_id,
            "traceId": request_id,
            "jobType": job.job_type.value,
            "createdAt": now,
            "notBefore": now,
            "expiresAt": input_delete,
            "idempotencyKey": f"job:{job.id}",
            "attempt": 1,
            "maxAttempts": job.max_attempts,
            "retention": {
                "inputDeleteAfter": input_delete,
                "successDeleteAfter": success_delete,
                "failureDeleteAfter": failure_delete,
                "deadLetterDeleteAfter": failure_delete,
                # These are durable patient capture assets, not disposable worker
                # scratch files. The worker owns and lists only scratch resources
                # it creates in subsequent retention registrations.
                "cleanupTargets": [],
            },
            "payload": job.request_payload,
        }
    )


async def publish_job(app, session: AsyncSession, job: Job) -> None:
    if job.queue_published_at is not None:
        return
    if not job.queue_envelope:
        raise ServiceError(500, "invalid_job_state", "The job is incomplete.")
    try:
        message_id = await app.state.job_queue.publish(job.queue_envelope)
    except QueueUnavailable as exc:
        raise ServiceError(
            503, "job_queue_unavailable", "The job is saved and awaiting delivery."
        ) from exc
    job.queue_message_id = message_id
    job.queue_published_at = utc_now()
    await session.commit()


def envelope_json(envelope: JobEnvelope) -> str:
    return json.dumps(
        envelope.model_dump(mode="json", by_alias=True),
        sort_keys=True,
        separators=(",", ":"),
    )

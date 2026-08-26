"""HMAC-authenticated worker callbacks, report rendering, and delete execution."""

from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import timedelta
from math import ceil
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Request
from pydantic import ValidationError
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..collaboration_common import append_audit_event
from ..dependencies import get_session
from ..errors import ServiceError
from ..internal_schemas import (
    DeletionExecuteRequest,
    DeletionExecuteResponse,
    ReportRenderRequest,
    ReportRenderResponse,
    WorkerResultNotification,
    WorkerRetentionRegistration,
)
from ..job_contracts import JobEnvelope
from ..models import (
    AccessEvent,
    AccessGrantResource,
    AnalysisRun,
    AnalyticsEvent,
    AuditEvent,
    CalibrationStatus,
    CandidateObservation,
    CaptureAsset,
    CaptureStatus,
    CaptureSet,
    CaptureView,
    ClinicianAccessGrant,
    ClinicianReview,
    ClinicianVerification,
    ConsentRecord,
    DataExportArtifact,
    DeletionRequest,
    DeletionStatus,
    Device,
    EntityTombstone,
    GeneratedArtifact,
    IdempotencyRecord,
    Job,
    JobStatus,
    JobType,
    LesionObservationLink,
    LesionRecord,
    MatchDecision,
    MatchDecisionValue,
    MatchProposal,
    ReportArtifact,
    ReviewAnnotation,
    ScanSession,
    ShareExchangeToken,
    ShareLink,
    ShareLinkResource,
    SyncChange,
    SyncCursor,
    SyncEntityState,
    User,
    UserRole,
    UserStatus,
    new_id,
    utc_now,
)
from ..object_storage import StorageError, StorageNotFound
from ..product_consent import DOCUMENT_ID, DOCUMENT_SHA256, DOCUMENT_VERSION
from ..product_schemas import (
    AnalysisRunCreate,
    CalibrationEvidence,
    CandidateObservationCreate,
)
from ..report_renderer import ReportRenderError, build_report_pdf
from .internal_assets import (
    _authenticate_worker,
    _cleanup_failed_object,
    _lock_writable_job,
)

router = APIRouter(tags=["internal worker lifecycle"])
MAX_INTERNAL_JSON_BYTES = 2_000_000


async def _signed_json(request: Request, session: AsyncSession, model, headers):
    body = await request.body()
    if len(body) > MAX_INTERNAL_JSON_BYTES:
        raise ServiceError(413, "request_too_large", "The request is too large.")
    await _authenticate_worker(
        request=request,
        session=session,
        body=body,
        service_id=headers[0],
        timestamp=headers[1],
        nonce=headers[2],
        content_sha256=headers[3],
        signature=headers[4],
    )
    try:
        return model.model_validate_json(body)
    except ValidationError as exc:
        raise ServiceError(
            422, "invalid_worker_payload", "The worker payload is invalid."
        ) from exc


def _headers(service_id, timestamp, nonce, content_sha256, signature):
    return service_id, timestamp, nonce, content_sha256, signature


def _result_hash(value: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


async def _persist_analysis_result(
    session: AsyncSession,
    *,
    job: Job,
    notification: WorkerResultNotification,
) -> str | None:
    existing = await session.scalar(
        select(AnalysisRun).where(AnalysisRun.worker_job_id == job.id)
    )
    if existing is not None:
        return existing.id
    raw_analysis = notification.result.get("analysis")
    if not isinstance(raw_analysis, dict):
        return None
    if raw_analysis.get("analysisOrigin") == "unavailable":
        return None
    payload = job.request_payload
    capture_view_id = str(payload.get("captureId", ""))
    view = await session.get(CaptureView, capture_view_id)
    if view is None or view.user_id != job.user_id:
        raise ServiceError(
            422, "analysis_capture_missing", "The analysis capture is missing."
        )
    capture_set = await session.get(CaptureSet, view.capture_set_id)
    asset = await session.get(CaptureAsset, view.asset_id)
    if capture_set is None or asset is None or asset.user_id != job.user_id:
        raise ServiceError(
            422, "analysis_capture_missing", "The analysis capture is missing."
        )

    raw_calibration = notification.result.get("calibration")
    calibration: CalibrationEvidence | None = None
    if raw_calibration is not None:
        if not isinstance(raw_calibration, dict):
            raise ServiceError(
                422, "invalid_calibration_result", "Calibration evidence is invalid."
            )
        if raw_calibration.get("captureViewId") != view.id:
            raise ServiceError(
                422, "invalid_calibration_result", "Calibration evidence is invalid."
            )
        evidence = {
            key: value
            for key, value in raw_calibration.items()
            if key not in {"calibrationId", "captureViewId"}
        }
        try:
            calibration = CalibrationEvidence.model_validate(evidence)
        except ValidationError as exc:
            raise ServiceError(
                422, "invalid_calibration_result", "Calibration evidence is invalid."
            ) from exc

    observations: list[CandidateObservationCreate] = []
    if raw_analysis.get("candidateMask") is not None:
        uncertainty = raw_analysis.get("uncertainty")
        limitations = (
            uncertainty.get("limitations", []) if isinstance(uncertainty, dict) else []
        )
        try:
            observations.append(
                CandidateObservationCreate.model_validate(
                    {
                        "captureViewId": view.id,
                        "anatomicalSite": view.anatomical_site,
                        "candidateMask": raw_analysis["candidateMask"],
                        "descriptors": raw_analysis["descriptors"],
                        "calibration": (
                            calibration.model_dump(mode="json", by_alias=True)
                            if calibration
                            else None
                        ),
                        "appearanceOutput": raw_analysis.get("appearanceOutput"),
                        "diseaseResearchOutput": raw_analysis.get(
                            "diseaseResearchOutput"
                        ),
                        "uncertainty": uncertainty,
                        "namedMesh": None,
                        "uvCoordinates": None,
                        "assetVersion": None,
                        "limitations": limitations,
                    }
                )
            )
        except (ValidationError, KeyError) as exc:
            raise ServiceError(
                422, "invalid_analysis_result", "The analysis result is invalid."
            ) from exc
    status_value = raw_analysis.get("status")
    completed_at = notification.completed_at if status_value == "complete" else None
    exact_result_hash = _result_hash(raw_analysis)
    try:
        body = AnalysisRunCreate.model_validate(
            {
                "requestedHeads": payload.get("requestedHeads", []),
                "status": status_value,
                "observations": [
                    value.model_dump(mode="json", by_alias=True)
                    for value in observations
                ],
                "inputOrigin": raw_analysis.get("inputOrigin"),
                "analysisOrigin": raw_analysis.get("analysisOrigin"),
                "sourceAssetSha256": [asset.content_sha256],
                "modelVersions": raw_analysis.get("modelVersions", {}),
                "artifactHashes": {"signed-worker-result": exact_result_hash},
                "abstentionReasons": raw_analysis.get("abstentionReasons", []),
                "startedAt": job.created_at,
                "completedAt": completed_at,
                "signedEnvelopeId": job.id,
            }
        )
    except ValidationError as exc:
        raise ServiceError(
            422, "invalid_analysis_result", "The analysis result is invalid."
        ) from exc
    run = AnalysisRun(
        user_id=job.user_id,
        capture_set_id=capture_set.id,
        requested_heads=[value.value for value in body.requested_heads],
        status=body.status,
        input_origin=body.input_origin,
        analysis_origin=body.analysis_origin,
        source_asset_sha256=body.source_asset_sha256,
        model_versions=body.model_versions,
        artifact_hashes=body.artifact_hashes,
        abstention_reasons=body.abstention_reasons,
        started_at=body.started_at,
        completed_at=body.completed_at,
        persisted=True,
        signed_envelope_id=body.signed_envelope_id,
        worker_job_id=job.id,
    )
    session.add(run)
    await session.flush()
    for item in body.observations:
        evidence = (
            item.calibration.model_dump(mode="json", by_alias=True)
            if item.calibration
            else None
        )
        session.add(
            CandidateObservation(
                user_id=job.user_id,
                analysis_run_id=run.id,
                capture_view_id=item.capture_view_id,
                region=capture_set.region,
                anatomical_site=(
                    item.anatomical_site.value if item.anatomical_site else None
                ),
                candidate_mask=item.candidate_mask.model_dump(
                    mode="json", by_alias=True
                ),
                descriptors=item.descriptors.model_dump(mode="json", by_alias=True),
                uncertainty=item.uncertainty.model_dump(mode="json", by_alias=True),
                appearance_output=(
                    item.appearance_output.model_dump(mode="json", by_alias=True)
                    if item.appearance_output
                    else None
                ),
                disease_research_output=(
                    item.disease_research_output.model_dump(mode="json", by_alias=True)
                    if item.disease_research_output
                    else None
                ),
                calibration_status=(
                    item.calibration.status
                    if item.calibration
                    else CalibrationStatus.NOT_ATTEMPTED
                ),
                calibration_evidence=evidence,
                calibration_evidence_sha256=(
                    _result_hash(evidence) if evidence is not None else None
                ),
                estimated_width_mm=(
                    item.calibration.estimated_width_mm if item.calibration else None
                ),
                estimated_height_mm=(
                    item.calibration.estimated_height_mm if item.calibration else None
                ),
                estimated_area_mm2=(
                    item.calibration.estimated_area_mm2 if item.calibration else None
                ),
                limitations=item.limitations,
            )
        )
    await session.flush()
    return run.id


def _artifact_refs(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, nested in value.items():
            if key == "artifactId" and isinstance(nested, str):
                found.add(nested)
            else:
                found.update(_artifact_refs(nested))
    elif isinstance(value, list):
        for nested in value:
            found.update(_artifact_refs(nested))
    return found


@router.post("/internal/v2/jobs/{job_id}/result")
async def store_job_result(
    job_id: str,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    service_id: Annotated[str | None, Header(alias="X-OralSight-Service")] = None,
    timestamp: Annotated[str | None, Header(alias="X-OralSight-Timestamp")] = None,
    nonce: Annotated[str | None, Header(alias="X-OralSight-Nonce")] = None,
    content_sha256: Annotated[
        str | None, Header(alias="X-OralSight-Content-SHA256")
    ] = None,
    signature: Annotated[str | None, Header(alias="X-OralSight-Signature")] = None,
):
    body = await _signed_json(
        request,
        session,
        WorkerResultNotification,
        _headers(service_id, timestamp, nonce, content_sha256, signature),
    )
    if body.job_id != job_id:
        raise ServiceError(422, "job_result_mismatch", "The job result does not match.")
    job = await session.get(Job, job_id)
    if job is None:
        raise ServiceError(404, "job_not_found", "The job was not found.")
    if job.result_outcome is not None:
        if (
            job.result_outcome == body.outcome
            and job.result_payload == body.result
            and job.reason_code == body.reason_code
        ):
            return {"accepted": True, "jobId": job.id, "status": job.status.value}
        raise ServiceError(409, "job_already_terminal", "The job is already terminal.")
    if job.cancellation_requested_at is not None and body.outcome != "cancelled":
        body = body.model_copy(
            update={
                "outcome": "cancelled",
                "result": {},
                "reason_code": "user_cancelled",
            }
        )
    output_refs = _artifact_refs(body.result)
    if job.job_type is JobType.ANALYSIS and body.outcome == "complete":
        analysis_id = await _persist_analysis_result(
            session, job=job, notification=body
        )
        if analysis_id:
            output_refs.add(analysis_id)
            job.resource_id = analysis_id
    job.result_outcome = body.outcome
    job.result_payload = body.result
    job.reason_code = body.reason_code
    job.output_refs = sorted(output_refs)
    job.completed_at = body.completed_at
    job.progress_percent = (
        100 if body.outcome in {"complete", "unavailable"} else job.progress_percent
    )
    if body.outcome in {"complete", "unavailable"}:
        job.status = JobStatus.SUCCEEDED
    elif body.outcome == "cancelled":
        job.status = JobStatus.CANCELLED
    else:
        job.status = JobStatus.FAILED
        job.error_code = body.reason_code
        job.error_message = "The background task could not be completed."
    append_audit_event(
        session,
        patient_user_id=job.user_id,
        actor_user_id=None,
        event_type="job.completed",
        resource_type="job",
        resource_id=job.id,
        request_id=request.state.request_id,
        details={"jobType": job.job_type.value, "outcome": body.outcome},
    )
    await session.commit()
    return {"accepted": True, "jobId": job.id, "status": job.status.value}


@router.post("/internal/v2/jobs/{job_id}/retention")
async def register_job_retention(
    job_id: str,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    service_id: Annotated[str | None, Header(alias="X-OralSight-Service")] = None,
    timestamp: Annotated[str | None, Header(alias="X-OralSight-Timestamp")] = None,
    nonce: Annotated[str | None, Header(alias="X-OralSight-Nonce")] = None,
    content_sha256: Annotated[
        str | None, Header(alias="X-OralSight-Content-SHA256")
    ] = None,
    signature: Annotated[str | None, Header(alias="X-OralSight-Signature")] = None,
):
    body = await _signed_json(
        request,
        session,
        WorkerRetentionRegistration,
        _headers(service_id, timestamp, nonce, content_sha256, signature),
    )
    job = await session.get(Job, job_id)
    if job is None:
        raise ServiceError(404, "job_not_found", "The job was not found.")
    if job.result_outcome is not None and job.result_outcome != body.outcome:
        raise ServiceError(
            409,
            "job_outcome_mismatch",
            "The retention outcome does not match the stored job result.",
        )
    if not job.queue_envelope:
        raise ServiceError(409, "invalid_job_state", "The job has no queue envelope.")
    try:
        expected = JobEnvelope.model_validate_json(job.queue_envelope).retention
    except ValidationError as exc:
        raise ServiceError(500, "invalid_job_state", "The job is incomplete.") from exc
    if body.retention != expected:
        raise ServiceError(
            422,
            "retention_policy_mismatch",
            "The retention policy does not match the queued job.",
        )
    job.retention_policy = body.retention.model_dump(mode="json", by_alias=True)
    await session.commit()
    return {"accepted": True, "jobId": job.id}


def _released_output(value: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    if value.get("enabled") is not True or value.get("gatePassed") is not True:
        return None
    return value


async def _report_observation(
    request: Request,
    session: AsyncSession,
    *,
    value: CandidateObservation,
    run: AnalysisRun,
    allowed_capture_sets: set[str],
    include_experimental: bool,
) -> tuple[dict[str, Any], int]:
    if run.capture_set_id not in allowed_capture_sets:
        raise ServiceError(
            422, "report_scan_mismatch", "An observation is not part of this scan."
        )
    view = await session.get(CaptureView, value.capture_view_id)
    if (
        view is None
        or view.user_id != value.user_id
        or view.capture_set_id != run.capture_set_id
        or view.deleted_at is not None
    ):
        raise ServiceError(
            409,
            "report_source_unavailable",
            "A selected observation capture is unavailable.",
        )
    asset = await session.get(CaptureAsset, view.asset_id)
    if (
        asset is None
        or asset.user_id != value.user_id
        or asset.deleted_at is not None
        or asset.status is not CaptureStatus.AVAILABLE
    ):
        raise ServiceError(
            409,
            "report_source_unavailable",
            "A selected observation capture is unavailable.",
        )
    try:
        image_bytes = await request.app.state.object_storage.get_bytes(
            asset.object_key, max_bytes=asset.byte_size
        )
    except StorageNotFound as exc:
        raise ServiceError(
            409,
            "report_source_unavailable",
            "A selected observation capture is unavailable.",
        ) from exc
    except StorageError as exc:
        raise ServiceError(
            503, "object_storage_unavailable", "Storage is unavailable."
        ) from exc
    if (
        len(image_bytes) != asset.byte_size
        or hashlib.sha256(image_bytes).hexdigest() != asset.content_sha256
    ):
        raise ServiceError(
            500,
            "stored_asset_corrupt",
            "A report source image failed integrity verification.",
        )
    return (
        {
            "observationId": value.id,
            "region": value.region.value,
            "anatomicalSite": value.anatomical_site,
            "capturedAt": view.captured_at.isoformat(),
            "imageBytes": image_bytes,
            "imageMediaType": asset.media_type,
            "imageSha256": asset.content_sha256,
            "candidateMask": value.candidate_mask,
            "descriptors": value.descriptors,
            "uncertainty": value.uncertainty,
            "qualityAccepted": view.quality_accepted,
            "qualityReasons": view.quality_reasons,
            "calibration": value.calibration_evidence,
            "appearance": _released_output(value.appearance_output),
            "experimental": (
                _released_output(value.disease_research_output)
                if include_experimental
                else None
            ),
            "namedMesh": value.named_mesh,
            "uvCoordinates": (
                [value.uv_u, value.uv_v]
                if value.uv_u is not None and value.uv_v is not None
                else None
            ),
            "assetVersion": value.asset_version,
            "limitations": value.limitations,
            "inputOrigin": run.input_origin.value,
            "analysisOrigin": run.analysis_origin.value,
            "modelVersions": run.model_versions,
            "artifactHashes": run.artifact_hashes,
        },
        len(image_bytes),
    )


async def _report_comparison(
    session: AsyncSession,
    *,
    decision: MatchDecision,
    user_id: str,
    comparison_jobs: list[Job],
    allowed_current_capture_sets: set[str],
    selected_observation_ids: set[str],
) -> dict[str, Any]:
    if decision.decision is not MatchDecisionValue.CONFIRMED:
        raise ServiceError(
            422,
            "comparison_not_user_confirmed",
            "Only user-confirmed comparisons may be included in a report.",
        )
    proposal = await session.get(MatchProposal, decision.proposal_id)
    if proposal is None or proposal.user_id != user_id:
        raise ServiceError(404, "resource_not_found", "A comparison was not found.")
    baseline = await session.get(
        CandidateObservation, proposal.candidate_prior_observation_id
    )
    current = await session.get(CandidateObservation, proposal.current_observation_id)
    if (
        baseline is None
        or current is None
        or baseline.user_id != user_id
        or current.user_id != user_id
        or baseline.region is not current.region
    ):
        raise ServiceError(404, "resource_not_found", "A comparison was not found.")
    current_run = await session.get(AnalysisRun, current.analysis_run_id)
    if (
        current.id not in selected_observation_ids
        or current_run is None
        or current_run.user_id != user_id
        or current_run.capture_set_id not in allowed_current_capture_sets
    ):
        raise ServiceError(
            422,
            "report_comparison_mismatch",
            "A comparison does not belong to a selected current observation.",
        )
    baseline_view = await session.get(CaptureView, baseline.capture_view_id)
    current_view = await session.get(CaptureView, current.capture_view_id)
    if baseline_view is None or current_view is None:
        raise ServiceError(404, "resource_not_found", "A comparison was not found.")
    matched_job: Job | None = None
    for candidate in comparison_jobs:
        payload = candidate.request_payload or {}
        if (
            payload.get("baselineCaptureId") == baseline_view.id
            and payload.get("currentCaptureId") == current_view.id
            and payload.get("userConfirmedMatch") is True
        ):
            matched_job = candidate
            break
    result = (
        (matched_job.result_payload or {}).get("comparison") if matched_job else None
    )
    if not isinstance(result, dict):
        result = {}
    exact_ids = (
        result.get("baselineCaptureId") == baseline_view.id
        and result.get("currentCaptureId") == current_view.id
        and result.get("userConfirmedMatch") is True
    )
    inlier = result.get("inlierRatio")
    reprojection = result.get("reprojectionErrorRatio")
    registration = result.get("registrationConfidence")
    change = result.get("normalizedChange")
    comparable = (
        exact_ids
        and result.get("comparable") is True
        and isinstance(inlier, int | float)
        and inlier >= 0.60
        and isinstance(reprojection, int | float)
        and reprojection <= 0.03
        and isinstance(registration, int | float)
        and isinstance(change, int | float)
    )
    suppressions = list(result.get("suppressionReasons") or [])
    if not comparable and not suppressions:
        suppressions = ["insufficient_comparable_data"]
    return {
        "decisionId": decision.id,
        "region": current.region.value,
        "baselineObservedAt": baseline_view.captured_at.isoformat(),
        "currentObservedAt": current_view.captured_at.isoformat(),
        "userConfirmedMatch": True,
        "matchProposalOrigin": proposal.proposal_origin.value,
        "candidateMatchScore": proposal.score,
        "comparable": comparable,
        "normalizedChange": change if comparable else None,
        "registrationConfidence": registration if exact_ids else None,
        "inlierRatio": inlier if exact_ids else None,
        "reprojectionErrorRatio": reprojection if exact_ids else None,
        "suppressionReasons": suppressions,
        "modelVersions": result.get("modelVersions") or proposal.model_versions,
    }


@router.post("/internal/v2/reports/render", response_model=ReportRenderResponse)
async def render_report(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    service_id: Annotated[str | None, Header(alias="X-OralSight-Service")] = None,
    timestamp: Annotated[str | None, Header(alias="X-OralSight-Timestamp")] = None,
    nonce: Annotated[str | None, Header(alias="X-OralSight-Nonce")] = None,
    content_sha256: Annotated[
        str | None, Header(alias="X-OralSight-Content-SHA256")
    ] = None,
    signature: Annotated[str | None, Header(alias="X-OralSight-Signature")] = None,
) -> ReportRenderResponse:
    body = await _signed_json(
        request,
        session,
        ReportRenderRequest,
        _headers(service_id, timestamp, nonce, content_sha256, signature),
    )
    job, user = await _lock_writable_job(
        session,
        job_id=body.job_id,
        expected_job_type=JobType.REPORT,
        not_found_message="The report job was not found.",
    )
    expected = {
        key: value for key, value in job.request_payload.items() if key != "kind"
    }
    submitted = body.model_dump(mode="json", by_alias=True, exclude={"job_id"})
    if submitted != expected:
        raise ServiceError(
            422, "report_job_mismatch", "The report request does not match its job."
        )
    existing = await session.scalar(
        select(ReportArtifact).where(ReportArtifact.signed_envelope_id == job.id)
    )
    if existing is not None:
        return ReportRenderResponse(
            artifact_id=existing.id,
            sha256=existing.content_sha256,
            byte_size=existing.byte_size,
        )
    scan = await session.get(ScanSession, body.scan_session_id)
    if scan is None or scan.user_id != job.user_id or scan.deleted_at is not None:
        raise ServiceError(404, "resource_not_found", "The scan was not found.")
    consent = await session.get(ConsentRecord, body.consent_record_id)
    if (
        consent is None
        or consent.user_id != job.user_id
        or not consent.accepted
        or consent.revoked_at is not None
        or consent.document_id != DOCUMENT_ID
        or consent.document_version != DOCUMENT_VERSION
        or consent.document_sha256 != DOCUMENT_SHA256
        or (scan.consent_record_id is not None and scan.consent_record_id != consent.id)
    ):
        raise ServiceError(
            409,
            "active_product_consent_required",
            "The report requires the active consent used for this scan.",
        )
    capture_sets = list(
        await session.scalars(
            select(CaptureSet).where(
                CaptureSet.scan_session_id == scan.id,
                CaptureSet.user_id == job.user_id,
                CaptureSet.deleted_at.is_(None),
            )
        )
    )
    capture_set_ids = {value.id for value in capture_sets}
    accepted_regions = {value.region.value for value in capture_sets if value.complete}
    observations: list[dict[str, Any]] = []
    model_versions: dict[str, str] = {}
    input_origins: set[str] = set()
    analysis_origins: set[str] = set()
    source_bytes = 0
    for observation_id in body.observation_ids:
        observation = await session.get(CandidateObservation, observation_id)
        if (
            observation is None
            or observation.user_id != job.user_id
            or observation.deleted_at is not None
        ):
            raise ServiceError(
                404, "resource_not_found", "An observation was not found."
            )
        run = await session.get(AnalysisRun, observation.analysis_run_id)
        if run is None or run.user_id != job.user_id:
            raise ServiceError(
                422, "report_scan_mismatch", "An observation is not part of this scan."
            )
        rendered_observation, byte_count = await _report_observation(
            request,
            session,
            value=observation,
            run=run,
            allowed_capture_sets=capture_set_ids,
            include_experimental=body.include_experimental_research_output,
        )
        source_bytes += byte_count
        if source_bytes > request.app.state.settings.report_source_max_bytes:
            raise ServiceError(
                413,
                "report_sources_too_large",
                "The selected report images exceed the report size limit.",
            )
        observations.append(rendered_observation)
        model_versions.update(run.model_versions)
        input_origins.add(run.input_origin.value)
        analysis_origins.add(run.analysis_origin.value)
    comparison_jobs = list(
        await session.scalars(
            select(Job)
            .where(
                Job.user_id == job.user_id,
                Job.job_type == JobType.COMPARISON,
                Job.result_outcome == "complete",
            )
            .order_by(Job.completed_at.desc(), Job.id.desc())
        )
    )
    comparisons: list[dict[str, Any]] = []
    for comparison_id in body.comparison_ids:
        decision = await session.get(MatchDecision, comparison_id)
        if decision is None or decision.user_id != job.user_id:
            raise ServiceError(404, "resource_not_found", "A comparison was not found.")
        comparison = await _report_comparison(
            session,
            decision=decision,
            user_id=job.user_id,
            comparison_jobs=comparison_jobs,
            allowed_current_capture_sets=capture_set_ids,
            selected_observation_ids=set(body.observation_ids),
        )
        comparisons.append(comparison)
        model_versions.update(comparison.get("modelVersions") or {})
    report_id = new_id()
    now = utc_now()
    try:
        pdf = await asyncio.to_thread(
            build_report_pdf,
            report_id=report_id,
            scan_id=scan.id,
            created_at=now.isoformat(),
            account={
                "reference": user.id[-8:],
                "createdAt": user.created_at.isoformat(),
            },
            consent={
                "documentId": consent.document_id,
                "documentVersion": consent.document_version,
                "documentSha256": consent.document_sha256,
                "acceptedAt": consent.accepted_at.isoformat(),
            },
            scan={
                "protocol": scan.protocol,
                "createdAt": scan.created_at.isoformat(),
                "completedAt": (
                    scan.completed_at.isoformat() if scan.completed_at else None
                ),
                "acceptedRegionCount": len(accepted_regions),
            },
            patient_profile=(
                body.patient_profile.model_dump(mode="json", by_alias=True)
                if body.patient_profile
                else None
            ),
            intake_summary=(
                body.intake_summary.model_dump(mode="json", by_alias=True)
                if body.intake_summary
                else None
            ),
            observations=observations,
            comparisons=comparisons,
            appointment_questions=body.appointment_questions,
            include_experimental=body.include_experimental_research_output,
        )
    except ReportRenderError as exc:
        raise ServiceError(
            422,
            "report_source_invalid",
            "A selected report image could not be rendered.",
        ) from exc
    digest = hashlib.sha256(pdf).hexdigest()
    object_key = f"users/{job.user_id}/reports/{report_id}.pdf"
    try:
        await request.app.state.object_storage.put_bytes(
            object_key, pdf, media_type="application/pdf", sha256=digest
        )
    except StorageError as exc:
        await _cleanup_failed_object(request, object_key)
        raise ServiceError(
            503, "object_storage_unavailable", "Storage is unavailable."
        ) from exc
    value = ReportArtifact(
        id=report_id,
        user_id=job.user_id,
        scan_session_ids=[scan.id],
        report_format="pdf",
        asset_id=report_id,
        object_key=object_key,
        media_type="application/pdf",
        content_sha256=digest,
        byte_size=len(pdf),
        locale=body.locale,
        accessible=False,
        input_origins=sorted(input_origins),
        analysis_origins=sorted(analysis_origins),
        model_versions=model_versions,
        signed_envelope_id=job.id,
        created_at=now,
        retention_expires_at=now + timedelta(days=365),
    )
    session.add(value)
    job.resource_id = value.id
    if value.id not in job.output_refs:
        job.output_refs = [*job.output_refs, value.id]
    append_audit_event(
        session,
        patient_user_id=job.user_id,
        actor_user_id=None,
        event_type="report.rendered",
        resource_type="report",
        resource_id=value.id,
        request_id=request.state.request_id,
        details={"format": "pdf", "byteSize": len(pdf)},
    )
    try:
        await session.commit()
    except BaseException:
        await session.rollback()
        await _cleanup_failed_object(request, object_key)
        raise
    return ReportRenderResponse(
        artifact_id=value.id,
        sha256=digest,
        byte_size=len(pdf),
    )


async def _delete_user_rows(
    session: AsyncSession,
    *,
    user_id: str,
    preserved_job_id: str,
    preserved_request_id: str,
) -> None:
    for model, column in [
        (ReviewAnnotation, ReviewAnnotation.clinician_user_id),
        (AccessEvent, AccessEvent.patient_user_id),
        (AccessEvent, AccessEvent.actor_user_id),
        (ClinicianVerification, ClinicianVerification.user_id),
        (LesionObservationLink, LesionObservationLink.user_id),
        (MatchDecision, MatchDecision.user_id),
        (MatchProposal, MatchProposal.user_id),
        (CandidateObservation, CandidateObservation.user_id),
        (AnalysisRun, AnalysisRun.user_id),
        (CaptureView, CaptureView.user_id),
        (CaptureSet, CaptureSet.user_id),
        (ReportArtifact, ReportArtifact.user_id),
        (GeneratedArtifact, GeneratedArtifact.user_id),
        (DataExportArtifact, DataExportArtifact.user_id),
        (AnalyticsEvent, AnalyticsEvent.user_id),
        (CaptureAsset, CaptureAsset.user_id),
        (LesionRecord, LesionRecord.user_id),
        (SyncChange, SyncChange.user_id),
        (SyncCursor, SyncCursor.user_id),
        (SyncEntityState, SyncEntityState.user_id),
        (EntityTombstone, EntityTombstone.user_id),
        (IdempotencyRecord, IdempotencyRecord.user_id),
        (AuditEvent, AuditEvent.user_id),
        (AuditEvent, AuditEvent.actor_user_id),
        (ClinicianVerification, ClinicianVerification.reviewer_user_id),
    ]:
        await session.execute(delete(model).where(column == user_id))
    grant_ids = list(
        await session.scalars(
            select(ClinicianAccessGrant.id).where(
                (ClinicianAccessGrant.patient_user_id == user_id)
                | (ClinicianAccessGrant.clinician_user_id == user_id)
            )
        )
    )
    if grant_ids:
        await session.execute(
            delete(AccessGrantResource).where(
                AccessGrantResource.grant_id.in_(grant_ids)
            )
        )
        await session.execute(
            delete(ClinicianReview).where(ClinicianReview.grant_id.in_(grant_ids))
        )
        await session.execute(
            delete(ClinicianAccessGrant).where(ClinicianAccessGrant.id.in_(grant_ids))
        )
    share_ids = list(
        await session.scalars(
            select(ShareLink.id).where(ShareLink.patient_user_id == user_id)
        )
    )
    if share_ids:
        await session.execute(
            delete(ShareExchangeToken).where(ShareExchangeToken.share_id.in_(share_ids))
        )
        await session.execute(
            delete(ShareLinkResource).where(ShareLinkResource.share_id.in_(share_ids))
        )
        await session.execute(delete(ShareLink).where(ShareLink.id.in_(share_ids)))
    await session.execute(
        delete(Job).where(Job.user_id == user_id, Job.id != preserved_job_id)
    )
    await session.execute(delete(ScanSession).where(ScanSession.user_id == user_id))
    await session.execute(delete(ConsentRecord).where(ConsentRecord.user_id == user_id))
    await session.execute(delete(Device).where(Device.user_id == user_id))
    await session.execute(
        delete(DeletionRequest).where(
            DeletionRequest.user_id == user_id,
            DeletionRequest.id != preserved_request_id,
        )
    )


async def _user_object_keys(session: AsyncSession, user_id: str) -> list[str]:
    keys = list(
        await session.scalars(
            select(CaptureAsset.object_key).where(CaptureAsset.user_id == user_id)
        )
    )
    keys.extend(
        await session.scalars(
            select(GeneratedArtifact.object_key).where(
                GeneratedArtifact.user_id == user_id
            )
        )
    )
    keys.extend(
        await session.scalars(
            select(DataExportArtifact.object_key).where(
                DataExportArtifact.user_id == user_id
            )
        )
    )
    keys.extend(
        value
        for value in await session.scalars(
            select(ReportArtifact.object_key).where(ReportArtifact.user_id == user_id)
        )
        if value
    )
    return sorted(set(keys))


async def _defer_deletion(
    session: AsyncSession,
    *,
    deletion: DeletionRequest,
    job: Job,
    code: str,
    message: str,
    retry_after_seconds: int,
) -> None:
    deletion.status = DeletionStatus.IN_PROGRESS
    deletion.error_code = code
    job.status = JobStatus.RUNNING
    job.error_code = None
    job.error_message = None
    await session.commit()
    raise ServiceError(
        503,
        code,
        message,
        headers={"Retry-After": str(max(1, retry_after_seconds))},
    )


@router.post(
    "/internal/v2/deletion-requests/{deletion_request_id}/execute",
    response_model=DeletionExecuteResponse,
)
async def execute_deletion(
    deletion_request_id: str,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    service_id: Annotated[str | None, Header(alias="X-OralSight-Service")] = None,
    timestamp: Annotated[str | None, Header(alias="X-OralSight-Timestamp")] = None,
    nonce: Annotated[str | None, Header(alias="X-OralSight-Nonce")] = None,
    content_sha256: Annotated[
        str | None, Header(alias="X-OralSight-Content-SHA256")
    ] = None,
    signature: Annotated[str | None, Header(alias="X-OralSight-Signature")] = None,
) -> DeletionExecuteResponse:
    body = await _signed_json(
        request,
        session,
        DeletionExecuteRequest,
        _headers(service_id, timestamp, nonce, content_sha256, signature),
    )
    deletion = await session.get(DeletionRequest, deletion_request_id)
    if (
        deletion is None
        or body.job_id != deletion.job_id
        or body.subject_account_id != deletion.user_id
    ):
        raise ServiceError(
            404, "deletion_request_not_found", "The deletion request was not found."
        )
    user = await session.scalar(
        select(User).where(User.id == deletion.user_id).with_for_update()
    )
    deletion = await session.scalar(
        select(DeletionRequest)
        .where(DeletionRequest.id == deletion_request_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if deletion is None:
        raise ServiceError(
            404, "deletion_request_not_found", "The deletion request was not found."
        )
    if deletion.status is DeletionStatus.COMPLETED:
        return DeletionExecuteResponse(
            deletion_request_id=deletion.id,
            status="complete",
            rotate_installation_key=True,
        )
    job = await session.scalar(
        select(Job)
        .where(Job.id == deletion.job_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if job is None or user is None or job.job_type is not JobType.DELETE_ALL:
        raise ServiceError(
            409, "invalid_deletion_state", "The deletion request is incomplete."
        )
    now = utc_now()
    deletion.status = DeletionStatus.IN_PROGRESS
    deletion.started_at = deletion.started_at or now
    job.started_at = job.started_at or now
    job.status = JobStatus.RUNNING
    latest_capability_expiry = await session.scalar(
        select(func.max(CaptureAsset.upload_capability_expires_at)).where(
            CaptureAsset.user_id == user.id
        )
    )
    if latest_capability_expiry is not None:
        if latest_capability_expiry.tzinfo is None:
            latest_capability_expiry = latest_capability_expiry.replace(
                tzinfo=now.tzinfo
            )
        # Legacy direct S3 PUTs could finish after URL expiry. The platform-held
        # upload lock is primary for new capabilities; retain this wait before
        # final delete/rescan/verification as migration defense in depth.
        candidate = latest_capability_expiry + timedelta(
            seconds=request.app.state.settings.upload_completion_quiet_seconds
        )
        current = deletion.upload_quiescence_until
        if current is not None and current.tzinfo is None:
            current = current.replace(tzinfo=now.tzinfo)
        if current is None or candidate > current:
            deletion.upload_quiescence_until = candidate

    object_keys = await _user_object_keys(session, user.id)
    try:
        for object_key in object_keys:
            await request.app.state.object_storage.delete(object_key)
    except StorageError as exc:
        await _defer_deletion(
            session,
            deletion=deletion,
            job=job,
            code="object_cleanup_retry_pending",
            message="Stored files are still being removed.",
            retry_after_seconds=5,
        )
        raise AssertionError("unreachable") from exc

    quiescence_until = deletion.upload_quiescence_until
    if quiescence_until is not None and quiescence_until.tzinfo is None:
        quiescence_until = quiescence_until.replace(tzinfo=now.tzinfo)
    if quiescence_until is not None and now < quiescence_until:
        job.progress_percent = max(job.progress_percent, 20)
        await _defer_deletion(
            session,
            deletion=deletion,
            job=job,
            code="upload_capability_quiescing",
            message="Issued upload links are expiring before final deletion.",
            retry_after_seconds=ceil((quiescence_until - now).total_seconds()),
        )

    # All issued write capabilities are now expired. Rescan the still-retained
    # rows, delete every known key again, and verify strongly consistent absence
    # before removing the rows that identify those keys.
    user_prefix = f"users/{user.id}/"
    object_keys = sorted(
        set(await _user_object_keys(session, user.id))
        | set(await request.app.state.object_storage.list_prefix(user_prefix))
    )
    try:
        for object_key in object_keys:
            await request.app.state.object_storage.delete(object_key)
        for object_key in object_keys:
            try:
                await request.app.state.object_storage.stat(object_key)
            except StorageNotFound:
                continue
            await _defer_deletion(
                session,
                deletion=deletion,
                job=job,
                code="object_cleanup_verification_pending",
                message="Stored-file deletion is still being verified.",
                retry_after_seconds=5,
            )
        remaining = await request.app.state.object_storage.list_prefix(user_prefix)
        if remaining:
            await _defer_deletion(
                session,
                deletion=deletion,
                job=job,
                code="object_cleanup_verification_pending",
                message="Stored-file deletion is still being verified.",
                retry_after_seconds=5,
            )
    except StorageError as exc:
        await _defer_deletion(
            session,
            deletion=deletion,
            job=job,
            code="object_cleanup_verification_pending",
            message="Stored-file deletion is still being verified.",
            retry_after_seconds=5,
        )
        raise AssertionError("unreachable") from exc
    await _delete_user_rows(
        session,
        user_id=user.id,
        preserved_job_id=job.id,
        preserved_request_id=deletion.id,
    )
    now = utc_now()
    user.oidc_subject = f"deleted:{new_id()}"
    user.role = UserRole.PATIENT
    user.status = UserStatus.SUSPENDED
    user.analytics_enabled = False
    user.analytics_policy_version = None
    user.analytics_updated_at = now
    deletion.status = DeletionStatus.COMPLETED
    deletion.completed_at = now
    deletion.error_code = None
    deletion.upload_quiescence_until = None
    # Keep only a keyed polling receipt for seven days, then scrub its link to the
    # deleted identity in the normal retention sweep.
    deletion.retention_expires_at = now + timedelta(days=7)
    job.status = JobStatus.RUNNING
    job.progress_percent = 95
    job.input_refs = [deletion.id]
    job.request_payload = {
        "kind": "delete_all",
        "deletionRequestId": deletion.id,
        "subjectAccountId": user.id,
        "scope": "all_oralsight_data",
        "rotateInstallationKey": True,
    }
    await session.commit()
    return DeletionExecuteResponse(
        deletion_request_id=deletion.id,
        status="complete",
        rotate_installation_key=True,
    )

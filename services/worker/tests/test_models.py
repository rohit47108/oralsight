from __future__ import annotations

from base64 import b64encode
from datetime import timedelta
from uuid import UUID

import pytest
from conftest import (
    ACCOUNT_ID,
    ASSET_ID,
    CAPTURE_ID,
    IMAGE_BYTES,
    JOB_ID,
    NOW,
    REQUEST_ID,
    TRACE_ID,
    analysis_envelope,
    asset_pointer,
    retention,
)
from pydantic import ValidationError

from oralsight_worker.models import (
    AnalysisOrigin,
    AnalysisStatus,
    CalibrationRequest,
    ComparePayload,
    DataExportEncryption,
    DataExportPayload,
    DeleteAllPayload,
    JobEnvelope,
    JobOutcome,
    JobType,
    MouthRegion,
    PriorAnalysisMetadata,
    ReconstructionPayload,
    ReconstructionPin,
    ReconstructionView,
    ReportPayload,
    ResultNotification,
    SummaryVideoGuidance,
    SummaryVideoObservation,
    SummaryVideoPayload,
)


def wrap(job_type: JobType, payload) -> JobEnvelope:
    return JobEnvelope(
        job_id=JOB_ID,
        request_id=REQUEST_ID,
        account_id=ACCOUNT_ID,
        trace_id=TRACE_ID,
        job_type=job_type,
        created_at=NOW,
        not_before=NOW,
        expires_at=NOW + timedelta(hours=12),
        idempotency_key=f"{job_type.value}:00000000-0000-4000-8000-000000000001",
        retention=retention(),
        payload=payload,
    )


def prior(capture_id: UUID) -> PriorAnalysisMetadata:
    return PriorAnalysisMetadata(
        capture_id=capture_id,
        region=MouthRegion.DORSAL_TONGUE,
        status=AnalysisStatus.COMPLETE,
        analysis_origin=AnalysisOrigin.LIVE_MODEL,
        quality_accepted=True,
        candidate_normalized_area=0.1,
        model_versions={"segmentation": "release-1"},
    )


def test_all_seven_job_payloads_validate() -> None:
    current = UUID("00000000-0000-4000-8000-000000000007")
    second_asset = asset_pointer(IMAGE_BYTES)
    second_asset.asset_id = UUID("00000000-0000-4000-8000-000000000008")
    comparison = ComparePayload(
        baseline_capture_id=CAPTURE_ID,
        current_capture_id=current,
        baseline_image=asset_pointer(),
        current_image=second_asset,
        region=MouthRegion.DORSAL_TONGUE,
        user_confirmed_match=True,
        baseline_analysis=prior(CAPTURE_ID),
        current_analysis=prior(current),
    )
    views = [
        ReconstructionView(
            capture_id=UUID(f"00000000-0000-4000-8000-{index:012d}"),
            image=asset_pointer(),
            region=MouthRegion.DORSAL_TONGUE,
            angle_label=label,
        )
        for index, label in enumerate(("center", "left", "right"), start=20)
    ]
    payloads = {
        JobType.COMPARISON: comparison,
        JobType.RECONSTRUCTION: ReconstructionPayload(
            capture_set_id=UUID("00000000-0000-4000-8000-000000000030"),
            views=views,
        ),
        JobType.REPORT: ReportPayload(
            scan_session_id=UUID("00000000-0000-4000-8000-000000000031"),
            observation_ids=[UUID("00000000-0000-4000-8000-000000000032")],
        ),
        JobType.SUMMARY_VIDEO: SummaryVideoPayload(
            scan_session_id=UUID("00000000-0000-4000-8000-000000000031"),
            report_id=UUID("00000000-0000-4000-8000-000000000033"),
            template_version="summary-v1",
            selected_observations=[
                SummaryVideoObservation(
                    observation_id=UUID("00000000-0000-4000-8000-000000000035"),
                    region=MouthRegion.DORSAL_TONGUE,
                    current_capture_id=CAPTURE_ID,
                    current_observed_at=NOW,
                    current_image=asset_pointer(),
                    quality_score=0.9,
                )
            ],
            guidance=SummaryVideoGuidance(
                code="neutral_seek_care_information", source="neutral"
            ),
        ),
        JobType.DATA_EXPORT: DataExportPayload(
            export_request_id=UUID("00000000-0000-4000-8000-000000000036"),
            encryption=DataExportEncryption(
                recipient_public_key_b64=b64encode(b"x" * 32).decode("ascii")
            ),
        ),
        JobType.DELETE_ALL: DeleteAllPayload(
            deletion_request_id=UUID("00000000-0000-4000-8000-000000000034"),
            subject_account_id=ACCOUNT_ID,
        ),
    }
    assert analysis_envelope().payload.kind is JobType.ANALYSIS
    for kind, payload in payloads.items():
        assert wrap(kind, payload).payload.kind is kind


def test_export_requires_a_raw_x25519_recipient_key() -> None:
    with pytest.raises(ValidationError):
        DataExportEncryption(recipient_public_key_b64="not-a-key")


def test_summary_video_rejects_unapproved_clinical_guidance() -> None:
    with pytest.raises(ValidationError, match="clinician-approved"):
        SummaryVideoGuidance(
            code="professional_review_suggested",
            source="neutral",
        )


def test_envelope_rejects_extra_fields_and_mismatched_type() -> None:
    raw = analysis_envelope().model_dump(mode="json", by_alias=True)
    raw["unexpectedClinicalText"] = "must not enter the queue"
    with pytest.raises(ValidationError):
        JobEnvelope.model_validate(raw)

    with pytest.raises(ValidationError):
        analysis_envelope(job_type=JobType.REPORT)


def test_retention_and_expiration_ceilings_are_enforced() -> None:
    too_long = retention().model_copy(
        update={"success_delete_after": NOW + timedelta(days=31)}
    )
    with pytest.raises(ValidationError, match="30 days"):
        analysis_envelope(retention=too_long)
    with pytest.raises(ValidationError, match="24 hours"):
        analysis_envelope(expires_at=NOW + timedelta(hours=25))


def test_live_analysis_cannot_request_fixture_origin() -> None:
    raw = analysis_envelope().model_dump(mode="json", by_alias=True)
    raw["payload"]["inputOrigin"] = "bundled_demo"
    with pytest.raises(ValidationError):
        JobEnvelope.model_validate(raw)


def test_calibration_request_is_version_and_marker_bound() -> None:
    request = CalibrationRequest(plane_confirmed=True)
    assert request.card_version == "oralsight-calibration-v1"
    assert request.marker_id == 17
    assert request.marker_side_mm == 20.0
    with pytest.raises(ValidationError):
        CalibrationRequest.model_validate(
            {
                "cardVersion": "unknown-card",
                "markerId": 17,
                "markerSideMm": 20.0,
                "planeConfirmed": True,
            }
        )


def test_reconstruction_needs_three_unique_views() -> None:
    view = ReconstructionView(
        capture_id=CAPTURE_ID,
        image=asset_pointer(),
        region=MouthRegion.DORSAL_TONGUE,
        angle_label="center",
    )
    with pytest.raises(ValidationError):
        ReconstructionPayload(
            capture_set_id=ASSET_ID,
            views=[view, view, view],
        )


def test_reconstruction_pin_requires_canonical_mesh_and_approved_rule() -> None:
    values = {
        "observation_id": UUID("00000000-0000-4000-8000-000000000040"),
        "region": MouthRegion.DORSAL_TONGUE,
        "mesh_name": "tongue_dorsal",
        "uv_coordinates": (0.4, 0.6),
        "asset_version": "mouth-map-v1",
        "observed_at": NOW,
        "status": "stable",
        "user_confirmed": True,
    }
    pin = ReconstructionPin(**values)
    assert pin.mesh_name == "tongue_dorsal"

    with pytest.raises(ValidationError, match="canonical mesh"):
        ReconstructionPin(**{**values, "mesh_name": "wrong_mesh"})
    with pytest.raises(ValidationError, match="normalized"):
        ReconstructionPin(**{**values, "uv_coordinates": (float("nan"), 0.5)})
    with pytest.raises(ValidationError, match="clinician-approved"):
        ReconstructionPin(
            **{
                **values,
                "status": "professional_review_suggested",
            }
        )


def test_envelope_cross_field_privacy_rules(envelope) -> None:
    raw = envelope.model_dump(mode="json", by_alias=True)
    raw["retention"]["inputDeleteAfter"] = (NOW + timedelta(hours=1)).isoformat()
    with pytest.raises(ValidationError, match="cannot precede"):
        JobEnvelope.model_validate(raw)

    raw = envelope.model_dump(mode="json", by_alias=True)
    raw["payload"]["image"]["sizeBytes"] = 1_750_001
    with pytest.raises(ValidationError, match="1,750,000"):
        JobEnvelope.model_validate(raw)


def test_result_notifications_require_coherent_terminal_details(envelope) -> None:
    with pytest.raises(ValidationError, match="require a reason"):
        ResultNotification(
            job_id=envelope.job_id,
            outcome=JobOutcome.FAILED,
            completed_at=NOW,
        )
    with pytest.raises(ValidationError, match="cannot include"):
        ResultNotification(
            job_id=envelope.job_id,
            outcome=JobOutcome.COMPLETE,
            completed_at=NOW,
            reason_code="unexpected_reason",
        )


def test_next_attempt_revalidates_the_envelope(envelope) -> None:
    next_envelope = envelope.next_attempt(not_before=NOW + timedelta(minutes=1))
    assert next_envelope.attempt == envelope.attempt + 1

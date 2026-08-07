from __future__ import annotations

import re
from base64 import b64encode
from io import BytesIO
from uuid import UUID

import cv2
import httpx
import numpy as np
import pytest
from conftest import CAPTURE_ID, IMAGE_BYTES, asset_pointer
from PIL import Image, ImageDraw

from oralsight_worker.auth import ServiceRequestSigner
from oralsight_worker.http_client import (
    InternalHttpClient,
    PermanentJobError,
    RetryableJobError,
)
from oralsight_worker.models import (
    AnalysisOrigin,
    AnalysisStatus,
    CalibrationRequest,
    ComparePayload,
    DataExportEncryption,
    DataExportPayload,
    DeleteAllPayload,
    JobOutcome,
    JobType,
    PriorAnalysisMetadata,
    ReconstructionPayload,
    ReconstructionView,
    ReportPayload,
    SummaryVideoGuidance,
    SummaryVideoObservation,
    SummaryVideoPayload,
    VideoCandidateMask,
)
from oralsight_worker.processors import (
    AnalysisProcessor,
    ComparisonProcessor,
    DataExportProcessor,
    DeleteAllProcessor,
    JobCancelled,
    JobContext,
    PlatformReporter,
    ProcessorRegistry,
    ReconstructionProcessor,
    ReportProcessor,
    SummaryVideoProcessor,
)


async def never_cancelled(_job_id: str) -> bool:
    return False


async def heartbeat(_job_id: str) -> None:
    return None


def context(envelope) -> JobContext:
    return JobContext(str(envelope.job_id), never_cancelled, heartbeat)


def internal_client(handler) -> tuple[InternalHttpClient, httpx.AsyncClient]:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return (
        InternalHttpClient(
            client=client,
            signer=ServiceRequestSigner("oralsight-worker", b"x" * 32),
            platform_api_url="https://platform.internal",
            inference_api_url="https://inference.internal",
            max_asset_bytes=8_000_000,
        ),
        client,
    )


def sharp_jpeg() -> bytes:
    image = Image.new("RGB", (192, 192), "white")
    draw = ImageDraw.Draw(image)
    for y in range(0, 192, 12):
        for x in range(0, 192, 12):
            color = "#842E3A" if (x // 12 + y // 12) % 2 else "#F2D1C9"
            draw.rectangle((x, y, x + 11, y + 11), fill=color)
    output = BytesIO()
    image.save(output, format="JPEG", quality=92)
    return output.getvalue()


def calibrated_capture() -> bytes:
    image = np.full((600, 800, 3), 255, dtype=np.uint8)
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    marker = cv2.aruco.generateImageMarker(dictionary, 17, 200)
    image[180:380, 60:260] = cv2.cvtColor(marker, cv2.COLOR_GRAY2BGR)
    ok, encoded = cv2.imencode(".png", image)
    assert ok
    return encoded.tobytes()


async def test_analysis_fetches_hash_verified_asset_and_calls_real_inference(
    envelope,
) -> None:
    seen = []

    async def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, request.url.path))
        assert request.headers["X-OralSight-Service"] == "oralsight-worker"
        if request.method == "GET":
            return httpx.Response(
                200, content=IMAGE_BYTES, headers={"Content-Type": "image/jpeg"}
            )
        body = await request.aread()
        assert b'"inputOrigin":"live_capture"' in body
        return httpx.Response(
            200,
            json={
                "captureId": str(CAPTURE_ID),
                "region": "dorsal_tongue",
                "status": "abstained",
                "analysisOrigin": "live_model",
            },
        )

    internal, raw = internal_client(handler)
    try:
        result = await AnalysisProcessor(internal).process(envelope, context(envelope))
    finally:
        await raw.aclose()
    assert result.outcome is JobOutcome.COMPLETE
    assert result.result["analysis"]["status"] == "abstained"
    assert seen == [
        ("GET", f"/internal/v2/assets/{envelope.payload.image.asset_id}/content"),
        ("POST", "/v1/analyze"),
    ]


async def test_analysis_returns_calibration_only_after_real_marker_gates(
    envelope,
) -> None:
    image = calibrated_capture()
    payload = envelope.payload.model_copy(
        update={
            "image": asset_pointer(image),
            "calibration": CalibrationRequest(plane_confirmed=True),
        }
    )
    job = envelope.model_copy(update={"payload": payload})

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(
                200, content=image, headers={"Content-Type": "image/jpeg"}
            )
        return httpx.Response(
            200,
            json={
                "captureId": str(CAPTURE_ID),
                "region": "dorsal_tongue",
                "status": "complete",
                "analysisOrigin": "live_model",
                "candidateMask": {
                    "polygon": [
                        [0.45, 0.383333],
                        [0.575, 0.383333],
                        [0.575, 0.466666],
                        [0.45, 0.466666],
                    ],
                    "boundingBox": [0.45, 0.383333, 0.125, 0.083333],
                    "normalizedArea": 5_000 / (800 * 600),
                },
            },
        )

    internal, raw = internal_client(handler)
    try:
        result = await AnalysisProcessor(internal).process(job, context(job))
    finally:
        await raw.aclose()

    calibration = result.result["calibration"]
    assert calibration["status"] == "valid"
    assert calibration["estimatedWidthMm"] == pytest.approx(10.0, abs=0.2)
    assert calibration["estimatedHeightMm"] == pytest.approx(5.0, abs=0.2)
    assert calibration["estimatedAreaMm2"] == pytest.approx(50.0, abs=3.0)
    assert calibration["gateReasons"] == []


async def test_asset_hash_mismatch_fails_without_calling_inference(envelope) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            200,
            content=b"different-same-length!",
            headers={"Content-Type": "image/jpeg"},
        )

    internal, raw = internal_client(handler)
    try:
        with pytest.raises(PermanentJobError):
            await AnalysisProcessor(internal).process(envelope, context(envelope))
    finally:
        await raw.aclose()
    assert calls == 1


async def test_local_reconstruction_abstains_on_undecodable_views(envelope) -> None:
    views = [
        ReconstructionView(
            capture_id=UUID(f"00000000-0000-4000-8000-{index:012d}"),
            image=asset_pointer(),
            region="dorsal_tongue",
            angle_label=angle,
        )
        for index, angle in enumerate(("center", "left", "right"), start=40)
    ]
    payload = ReconstructionPayload(
        capture_set_id=UUID("00000000-0000-4000-8000-000000000050"),
        views=views,
    )
    reconstruction_job = envelope.model_copy(
        update={"job_type": JobType.RECONSTRUCTION, "payload": payload}
    )

    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return httpx.Response(
            200,
            content=IMAGE_BYTES,
            headers={"Content-Type": "image/jpeg"},
        )

    internal, raw = internal_client(handler)
    try:
        result = await ReconstructionProcessor(internal).process(
            reconstruction_job, context(reconstruction_job)
        )
    finally:
        await raw.aclose()
    assert result.outcome is JobOutcome.UNAVAILABLE
    assert result.reason_code == "insufficient_usable_reconstruction_views"
    assert result.result["reconstruction"]["status"] == "abstained"
    assert result.result["reconstruction"]["acceptedViewCount"] == 0
    assert calls == [f"/internal/v2/assets/{asset_pointer().asset_id}/content"] * 3


async def test_report_accepts_only_a_real_pdf_artifact(envelope) -> None:
    payload = ReportPayload(
        scan_session_id=UUID("00000000-0000-4000-8000-000000000060"),
        observation_ids=[UUID("00000000-0000-4000-8000-000000000061")],
    )
    report_job = envelope.model_copy(
        update={"job_type": JobType.REPORT, "payload": payload}
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "artifactId": "00000000-0000-4000-8000-000000000062",
                "mediaType": "application/pdf",
                "sha256": "a" * 64,
            },
        )

    internal, raw = internal_client(handler)
    try:
        result = await ReportProcessor(internal).process(
            report_job, context(report_job)
        )
    finally:
        await raw.aclose()
    assert result.result["report"]["mediaType"] == "application/pdf"


async def test_json_response_size_is_bounded() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"{" + b"x" * 100 + b"}")

    internal, raw = internal_client(handler)
    try:
        with pytest.raises(PermanentJobError, match="upstream_response_too_large"):
            await internal.post_json(
                "https://platform.internal", "/internal/test", {}, max_response_bytes=10
            )
    finally:
        await raw.aclose()


async def test_generated_artifact_hash_is_checked_before_upload() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(500)

    internal, raw = internal_client(handler)
    try:
        with pytest.raises(PermanentJobError, match="generated_artifact_hash_mismatch"):
            await internal.upload_generated_artifact(
                job_id="00000000-0000-4000-8000-000000000001",
                purpose="summary_video",
                filename="summary.mp4",
                media_type="video/mp4",
                data=b"real-video-bytes",
                sha256="0" * 64,
                manifest={"captionsIncluded": True},
            )
    finally:
        await raw.aclose()
    assert calls == 0


@pytest.mark.parametrize(
    ("status", "error_type"),
    [(400, PermanentJobError), (503, RetryableJobError)],
)
async def test_upstream_http_errors_are_classified(status, error_type) -> None:
    internal, raw = internal_client(
        lambda request: httpx.Response(status, json={"private": "not logged"})
    )
    try:
        with pytest.raises(error_type):
            await internal.post_json("https://platform.internal", "/internal/test", {})
    finally:
        await raw.aclose()


def prior(capture_id: UUID) -> PriorAnalysisMetadata:
    return PriorAnalysisMetadata(
        capture_id=capture_id,
        region="dorsal_tongue",
        status=AnalysisStatus.COMPLETE,
        analysis_origin=AnalysisOrigin.LIVE_MODEL,
        quality_accepted=True,
        candidate_normalized_area=0.1,
        model_versions={"segmentation": "release-1"},
    )


async def test_comparison_fetches_both_assets_and_calls_inference(envelope) -> None:
    current_id = UUID("00000000-0000-4000-8000-000000000071")
    current_asset = asset_pointer()
    current_asset.asset_id = UUID("00000000-0000-4000-8000-000000000072")
    payload = ComparePayload(
        baseline_capture_id=CAPTURE_ID,
        current_capture_id=current_id,
        baseline_image=asset_pointer(),
        current_image=current_asset,
        region="dorsal_tongue",
        user_confirmed_match=True,
        baseline_analysis=prior(CAPTURE_ID),
        current_analysis=prior(current_id),
    )
    job = envelope.model_copy(
        update={"job_type": JobType.COMPARISON, "payload": payload}
    )
    calls = []

    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.method == "GET":
            return httpx.Response(
                200, content=IMAGE_BYTES, headers={"Content-Type": "image/jpeg"}
            )
        body = await request.aread()
        assert b'"userConfirmedMatch":true' in body
        return httpx.Response(
            200,
            json={
                "baselineCaptureId": str(CAPTURE_ID),
                "currentCaptureId": str(current_id),
                "comparable": False,
            },
        )

    internal, raw = internal_client(handler)
    try:
        result = await ComparisonProcessor(internal).process(job, context(job))
    finally:
        await raw.aclose()
    assert result.result["comparison"]["comparable"] is False
    assert calls[-1] == "/v1/compare"
    assert len(calls) == 3


async def test_local_artifact_processors_publish_real_glb_and_mp4(
    envelope,
) -> None:
    image_bytes = sharp_jpeg()
    image_pointer = asset_pointer(image_bytes)
    views = [
        ReconstructionView(
            capture_id=UUID(f"00000000-0000-4000-8000-{index:012d}"),
            image=image_pointer,
            region="dorsal_tongue",
            angle_label=angle,
        )
        for index, angle in enumerate(("center", "left", "right"), start=80)
    ]
    reconstruction_job = envelope.model_copy(
        update={
            "job_type": JobType.RECONSTRUCTION,
            "payload": ReconstructionPayload(
                capture_set_id=UUID("00000000-0000-4000-8000-000000000090"),
                views=views,
            ),
        }
    )
    video_job = envelope.model_copy(
        update={
            "job_type": JobType.SUMMARY_VIDEO,
            "payload": SummaryVideoPayload(
                scan_session_id=UUID("00000000-0000-4000-8000-000000000091"),
                report_id=UUID("00000000-0000-4000-8000-000000000092"),
                template_version="summary-v1",
                selected_observations=[
                    SummaryVideoObservation(
                        observation_id=UUID("00000000-0000-4000-8000-000000000097"),
                        region="dorsal_tongue",
                        current_capture_id=views[0].capture_id,
                        current_observed_at=envelope.created_at,
                        current_image=image_pointer,
                        current_candidate_mask=VideoCandidateMask(
                            polygon=[(0.2, 0.2), (0.7, 0.25), (0.55, 0.75)],
                            bounding_box=(0.2, 0.2, 0.5, 0.55),
                            normalized_area=0.14,
                        ),
                        quality_score=0.92,
                    )
                ],
                guidance=SummaryVideoGuidance(
                    code="neutral_seek_care_information", source="neutral"
                ),
            ),
        }
    )

    uploaded: list[bytes] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(
                200,
                content=image_bytes,
                headers={"Content-Type": "image/jpeg"},
            )
        assert request.url.path == "/internal/v2/assets/generated"
        body = await request.aread()
        uploaded.append(body)
        sha_match = re.search(rb'"sha256":"([a-f0-9]{64})"', body)
        assert sha_match is not None
        media_type = (
            "model/gltf-binary"
            if b'"purpose":"reconstruction"' in body
            else "video/mp4"
        )
        return httpx.Response(
            200,
            json={
                "artifactId": f"00000000-0000-4000-8000-{93 + len(uploaded):012d}",
                "sha256": sha_match.group(1).decode(),
                "mediaType": media_type,
            },
        )

    internal, raw = internal_client(handler)
    try:
        reconstruction = await ReconstructionProcessor(internal).process(
            reconstruction_job, context(reconstruction_job)
        )
        video = await SummaryVideoProcessor(internal).process(
            video_job, context(video_job)
        )
    finally:
        await raw.aclose()
    assert reconstruction.outcome is JobOutcome.COMPLETE
    assert (
        reconstruction.result["reconstruction"]["manifest"]["notAnatomicalDigitalTwin"]
        is True
    )
    assert video.result["summaryVideo"]["captionsIncluded"] is True
    assert video.result["summaryVideo"]["manifest"]["notForDiagnosis"] is True
    assert len(uploaded) == 2
    assert b"glTF" in uploaded[0]
    assert b"ftyp" in uploaded[1]
    assert b"avc1" in uploaded[1]
    assert b'"captionMode":"burned_in"' in uploaded[1]
    assert b"This result is not a diagnosis." in uploaded[1]


async def test_delete_all_and_platform_callbacks_are_real_internal_calls(
    envelope,
) -> None:
    deletion_id = UUID("00000000-0000-4000-8000-000000000095")
    payload = DeleteAllPayload(
        deletion_request_id=deletion_id,
        subject_account_id=envelope.account_id,
    )
    job = envelope.model_copy(
        update={"job_type": JobType.DELETE_ALL, "payload": payload}
    )
    paths = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        if request.url.path.endswith("/execute"):
            return httpx.Response(
                200,
                json={"deletionRequestId": str(deletion_id), "status": "complete"},
            )
        return httpx.Response(200, json={"accepted": True})

    internal, raw = internal_client(handler)
    reporter = PlatformReporter(internal)
    try:
        result = await DeleteAllProcessor(internal).process(job, context(job))
        await reporter.report(job, JobOutcome.COMPLETE, result=result.result)
        await reporter.register_retention(job, JobOutcome.COMPLETE)
    finally:
        await raw.aclose()
    assert result.result["deletion"]["status"] == "complete"
    assert paths == [
        f"/internal/v2/deletion-requests/{deletion_id}/execute",
        f"/internal/v2/jobs/{job.job_id}/result",
        f"/internal/v2/jobs/{job.job_id}/retention",
    ]


async def test_portable_data_export_is_public_key_encrypted(envelope) -> None:
    export_request_id = UUID("00000000-0000-4000-8000-000000000098")
    payload = DataExportPayload(
        export_request_id=export_request_id,
        encryption=DataExportEncryption(
            recipient_public_key_b64=b64encode(b"r" * 32).decode("ascii")
        ),
    )
    job = envelope.model_copy(
        update={"job_type": JobType.DATA_EXPORT, "payload": payload}
    )

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/internal/v2/exports/render"
        body = await request.aread()
        assert b'"scope":"all_portable_data"' in body
        assert b'"includeFiles":true' in body
        return httpx.Response(
            200,
            json={
                "exportRequestId": str(export_request_id),
                "status": "complete",
                "artifactId": "00000000-0000-4000-8000-000000000099",
                "mediaType": "application/vnd.oralsight.export",
                "sha256": "a" * 64,
                "byteSize": 4_096,
                "encryption": {
                    "scheme": "x25519-hkdf-sha256-aes-256-gcm",
                    "ephemeralPublicKeyB64": b64encode(b"e" * 32).decode("ascii"),
                    "saltB64": b64encode(b"s" * 16).decode("ascii"),
                    "nonceB64": b64encode(b"n" * 12).decode("ascii"),
                },
            },
        )

    internal, raw = internal_client(handler)
    try:
        result = await DataExportProcessor(internal).process(job, context(job))
    finally:
        await raw.aclose()

    assert result.outcome is JobOutcome.COMPLETE
    assert result.result["dataExport"]["artifactId"].endswith("99")
    assert (
        result.result["dataExport"]["encryption"]["scheme"]
        == "x25519-hkdf-sha256-aes-256-gcm"
    )


async def test_cancellation_checkpoint_and_missing_registry_entry(envelope) -> None:
    async def cancelled(_job_id: str) -> bool:
        return True

    with pytest.raises(JobCancelled):
        await JobContext(str(envelope.job_id), cancelled, heartbeat).checkpoint()
    with pytest.raises(PermanentJobError, match="unsupported_job_type"):
        ProcessorRegistry({}).get(JobType.ANALYSIS)

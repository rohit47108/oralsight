"""Real orchestration processors; unavailable dependencies never yield fixtures."""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol, cast
from uuid import UUID, uuid5

from .calibration import (
    CALIBRATION_VERSION,
    CARD_VERSION,
    MARKER_SIDE_MM,
    estimate_calibration,
)
from .http_client import InternalHttpClient, PermanentJobError
from .local_artifacts import (
    LocalArtifact,
    SourceView,
    SurfaceAbstention,
    build_observation_surface_from_evidence,
    build_summary_video,
    inspect_source_view,
)
from .models import (
    AnalyzePayload,
    ComparePayload,
    DataExportPayload,
    DeleteAllPayload,
    JobEnvelope,
    JobOutcome,
    JobType,
    ProcessorResult,
    ReconstructionPayload,
    ReportPayload,
    ResultNotification,
    SummaryVideoPayload,
)


class JobCancelled(Exception):
    pass


@dataclass(frozen=True, slots=True)
class JobContext:
    job_id: str
    cancellation_check: Callable[[str], Awaitable[bool]]
    heartbeat: Callable[[str], Awaitable[None]]

    async def checkpoint(self) -> None:
        if await self.cancellation_check(self.job_id):
            raise JobCancelled
        await self.heartbeat(self.job_id)


class JobProcessor(Protocol):
    async def process(
        self, envelope: JobEnvelope, context: JobContext
    ) -> ProcessorResult: ...


def _upstream_unavailable(value: dict[str, Any]) -> ProcessorResult | None:
    if value.get("status") != "unavailable":
        return None
    reason = value.get("reasonCode")
    if not isinstance(reason, str) or not re.fullmatch(r"[a-z0-9_]{3,64}", reason):
        raise PermanentJobError("invalid_upstream_response")
    return ProcessorResult(
        outcome=JobOutcome.UNAVAILABLE,
        reason_code=reason,
        result={},
    )


@dataclass(slots=True)
class AnalysisProcessor:
    http: InternalHttpClient

    async def process(
        self, envelope: JobEnvelope, context: JobContext
    ) -> ProcessorResult:
        payload = cast(AnalyzePayload, envelope.payload)
        await context.checkpoint()
        image = await self.http.get_asset(payload.image)
        calibration: dict[str, Any] | None = None
        try:
            await context.checkpoint()
            metadata = {
                "contractVersion": payload.contract_version,
                "captureId": str(payload.capture_id),
                "selectedRegion": payload.selected_region.value,
                "inputOrigin": payload.input_origin,
                "requestedHeads": [head.value for head in payload.requested_heads],
            }
            if payload.calibration is not None:
                metadata["calibration"] = payload.calibration.model_dump(
                    by_alias=True,
                    mode="json",
                )
            result = await self.http.post_multipart(
                "/v1/analyze",
                data={"metadata": json.dumps(metadata, separators=(",", ":"))},
                files={
                    "image": (
                        "capture",
                        image,
                        payload.image.media_type,
                    )
                },
            )
            if payload.calibration is not None:
                candidate = result.get("candidateMask")
                bounding_box: tuple[float, float, float, float] | None = None
                candidate_polygon: tuple[tuple[float, float], ...] | None = None
                normalized_area: float | None = None
                if isinstance(candidate, dict):
                    raw_box = candidate.get("boundingBox")
                    raw_polygon = candidate.get("polygon")
                    raw_area = candidate.get("normalizedArea")
                    if (
                        isinstance(raw_box, list)
                        and len(raw_box) == 4
                        and all(isinstance(value, int | float) for value in raw_box)
                    ):
                        bounding_box = cast(
                            tuple[float, float, float, float],
                            tuple(float(value) for value in raw_box),
                        )
                    if (
                        isinstance(raw_polygon, list)
                        and len(raw_polygon) >= 3
                        and all(
                            isinstance(point, list)
                            and len(point) == 2
                            and all(isinstance(value, int | float) for value in point)
                            for point in raw_polygon
                        )
                    ):
                        candidate_polygon = tuple(
                            (float(point[0]), float(point[1])) for point in raw_polygon
                        )
                    if isinstance(raw_area, int | float):
                        normalized_area = float(raw_area)
                estimate = await asyncio.to_thread(
                    estimate_calibration,
                    image,
                    bounding_box=bounding_box,
                    candidate_polygon=candidate_polygon,
                    normalized_area=normalized_area,
                    plane_confirmed=payload.calibration.plane_confirmed,
                )
                valid = estimate.valid
                calibration = {
                    "calibrationId": str(
                        uuid5(envelope.job_id, "physical-calibration")
                    ),
                    "captureViewId": str(payload.capture_id),
                    "status": "valid" if valid else "invalid",
                    "method": "versioned_reference_card",
                    "cardVersion": CARD_VERSION,
                    "markerId": (
                        str(estimate.marker_id)
                        if estimate.marker_id is not None
                        else None
                    ),
                    "referenceWidthMm": MARKER_SIDE_MM if valid else None,
                    "millimetersPerPixel": estimate.millimeters_per_pixel,
                    "estimatedWidthMm": estimate.estimated_width_mm,
                    "estimatedHeightMm": estimate.estimated_height_mm,
                    "estimatedAreaMm2": estimate.estimated_area_mm2,
                    "confidence": estimate.confidence if valid else None,
                    "gateReasons": list(estimate.reasons),
                    "calibratedAt": (
                        envelope.created_at.isoformat().replace("+00:00", "Z")
                        if valid
                        else None
                    ),
                    "modelVersions": {"calibration": CALIBRATION_VERSION},
                    "measurementLabel": "calibrated estimate",
                }
        finally:
            image = b""
        await context.checkpoint()
        if result.get("captureId") != str(payload.capture_id):
            raise PermanentJobError("invalid_analysis_response")
        if result.get("region") != payload.selected_region.value:
            raise PermanentJobError("invalid_analysis_response")
        if result.get("status") not in {
            "complete",
            "abstained",
            "unsupported",
            "failed",
        }:
            raise PermanentJobError("invalid_analysis_response")
        return ProcessorResult(
            outcome=JobOutcome.COMPLETE,
            result={
                "analysis": result,
                **({"calibration": calibration} if calibration is not None else {}),
            },
        )


@dataclass(slots=True)
class ComparisonProcessor:
    http: InternalHttpClient

    async def process(
        self, envelope: JobEnvelope, context: JobContext
    ) -> ProcessorResult:
        payload = cast(ComparePayload, envelope.payload)
        await context.checkpoint()
        baseline = await self.http.get_asset(payload.baseline_image)
        current = b""
        try:
            await context.checkpoint()
            current = await self.http.get_asset(payload.current_image)
            metadata = {
                "contractVersion": payload.contract_version,
                "baselineCaptureId": str(payload.baseline_capture_id),
                "currentCaptureId": str(payload.current_capture_id),
                "region": payload.region.value,
                "userConfirmedMatch": payload.user_confirmed_match,
                "inputOrigin": payload.input_origin,
                "baselineAnalysis": payload.baseline_analysis.model_dump(
                    mode="json", by_alias=True
                ),
                "currentAnalysis": payload.current_analysis.model_dump(
                    mode="json", by_alias=True
                ),
            }
            result = await self.http.post_multipart(
                "/v1/compare",
                data={"metadata": json.dumps(metadata, separators=(",", ":"))},
                files={
                    "baseline_image": (
                        "baseline",
                        baseline,
                        payload.baseline_image.media_type,
                    ),
                    "current_image": (
                        "current",
                        current,
                        payload.current_image.media_type,
                    ),
                },
            )
        finally:
            baseline = b""
            current = b""
        await context.checkpoint()
        if result.get("baselineCaptureId") != str(payload.baseline_capture_id):
            raise PermanentJobError("invalid_comparison_response")
        if result.get("currentCaptureId") != str(payload.current_capture_id):
            raise PermanentJobError("invalid_comparison_response")
        if not isinstance(result.get("comparable"), bool):
            raise PermanentJobError("invalid_comparison_response")
        return ProcessorResult(
            outcome=JobOutcome.COMPLETE, result={"comparison": result}
        )


@dataclass(slots=True)
class ReconstructionProcessor:
    http: InternalHttpClient

    async def process(
        self, envelope: JobEnvelope, context: JobContext
    ) -> ProcessorResult:
        payload = cast(ReconstructionPayload, envelope.payload)
        evidence: list[dict[str, Any]] = []
        for view in payload.views:
            await context.checkpoint()
            image = await self.http.get_asset(view.image)
            try:
                evidence.append(
                    await asyncio.to_thread(
                        inspect_source_view,
                        SourceView(view=view, data=image),
                    )
                )
            finally:
                image = b""
        await context.checkpoint()
        generated_at = envelope.created_at.isoformat().replace("+00:00", "Z")
        rendered = await asyncio.to_thread(
            build_observation_surface_from_evidence,
            evidence,
            capture_set_id=str(payload.capture_set_id),
            calibration_id=(
                str(payload.calibration_id) if payload.calibration_id else None
            ),
            generated_at=generated_at,
            pins=payload.pins,
        )
        await context.checkpoint()
        if isinstance(rendered, SurfaceAbstention):
            return ProcessorResult(
                outcome=JobOutcome.UNAVAILABLE,
                reason_code=rendered.reason_code,
                result={"reconstruction": rendered.manifest},
            )
        published = await self._publish(envelope, rendered)
        await context.checkpoint()
        return ProcessorResult(
            outcome=JobOutcome.COMPLETE,
            result={
                "reconstruction": {
                    **published,
                    "approximationLabel": "oral observation surface",
                    "algorithmVersion": rendered.manifest["algorithmVersion"],
                    "quality": {
                        "status": rendered.manifest["status"],
                        "score": rendered.manifest["qualityScore"],
                        "acceptedViewCount": rendered.manifest["acceptedViewCount"],
                        "sourceViewCount": rendered.manifest["sourceViewCount"],
                        "abstentionReasons": rendered.manifest["abstentionReasons"],
                    },
                    "manifest": rendered.manifest,
                }
            },
        )

    async def _publish(
        self, envelope: JobEnvelope, artifact: LocalArtifact
    ) -> dict[str, Any]:
        result = await self.http.upload_generated_artifact(
            job_id=str(envelope.job_id),
            purpose="reconstruction",
            filename=artifact.filename,
            media_type=artifact.media_type,
            data=artifact.data,
            sha256=artifact.sha256,
            manifest=artifact.manifest,
        )
        if (
            not isinstance(result.get("artifactId"), str)
            or result.get("mediaType") != artifact.media_type
            or result.get("sha256") != artifact.sha256
        ):
            raise PermanentJobError("invalid_generated_artifact_response")
        return {
            "artifactId": result["artifactId"],
            "mediaType": artifact.media_type,
            "sha256": artifact.sha256,
            "byteSize": len(artifact.data),
        }


@dataclass(slots=True)
class ReportProcessor:
    http: InternalHttpClient

    async def process(
        self, envelope: JobEnvelope, context: JobContext
    ) -> ProcessorResult:
        payload = cast(ReportPayload, envelope.payload)
        await context.checkpoint()
        result = await self.http.post_json(
            self.http.platform_api_url,
            "/internal/v2/reports/render",
            {
                "jobId": str(envelope.job_id),
                **payload.model_dump(mode="json", by_alias=True, exclude={"kind"}),
            },
        )
        await context.checkpoint()
        if unavailable := _upstream_unavailable(result):
            return unavailable
        if (
            not isinstance(result.get("artifactId"), str)
            or result.get("mediaType") != "application/pdf"
            or not isinstance(result.get("sha256"), str)
        ):
            raise PermanentJobError("invalid_report_response")
        return ProcessorResult(outcome=JobOutcome.COMPLETE, result={"report": result})


@dataclass(slots=True)
class SummaryVideoProcessor:
    http: InternalHttpClient

    async def process(
        self, envelope: JobEnvelope, context: JobContext
    ) -> ProcessorResult:
        payload = cast(SummaryVideoPayload, envelope.payload)
        await context.checkpoint()
        generated_at = envelope.created_at.isoformat().replace("+00:00", "Z")
        pointers = {
            observation.current_image.asset_id: observation.current_image
            for observation in payload.selected_observations
        }
        pointers.update(
            {
                observation.baseline_image.asset_id: observation.baseline_image
                for observation in payload.selected_observations
                if observation.baseline_image is not None
            }
        )
        sources: dict[UUID, bytes] = {}
        try:
            for asset_id, pointer in pointers.items():
                await context.checkpoint()
                sources[asset_id] = await self.http.get_asset(pointer)
            artifact = await asyncio.to_thread(
                build_summary_video,
                payload,
                sources=sources,
                generated_at=generated_at,
            )
        except RuntimeError:
            return ProcessorResult(
                outcome=JobOutcome.UNAVAILABLE,
                reason_code="local_summary_video_render_failed",
                result={
                    "summaryVideo": {
                        "status": "abstained",
                        "captionsIncluded": False,
                        "disclaimer": payload.disclaimer,
                    }
                },
            )
        finally:
            sources.clear()
        await context.checkpoint()
        result = await self.http.upload_generated_artifact(
            job_id=str(envelope.job_id),
            purpose="summary_video",
            filename=artifact.filename,
            media_type=artifact.media_type,
            data=artifact.data,
            sha256=artifact.sha256,
            manifest=artifact.manifest,
        )
        if (
            not isinstance(result.get("artifactId"), str)
            or result.get("mediaType") != artifact.media_type
            or result.get("sha256") != artifact.sha256
        ):
            raise PermanentJobError("invalid_generated_artifact_response")
        await context.checkpoint()
        return ProcessorResult(
            outcome=JobOutcome.COMPLETE,
            result={
                "summaryVideo": {
                    "artifactId": result["artifactId"],
                    "mediaType": artifact.media_type,
                    "sha256": artifact.sha256,
                    "byteSize": len(artifact.data),
                    "captionsIncluded": True,
                    "captionMode": "burned_in",
                    "audioIncluded": False,
                    "rendererVersion": artifact.manifest["rendererVersion"],
                    "manifest": artifact.manifest,
                }
            },
        )


@dataclass(slots=True)
class DataExportProcessor:
    http: InternalHttpClient

    async def process(
        self, envelope: JobEnvelope, context: JobContext
    ) -> ProcessorResult:
        payload = cast(DataExportPayload, envelope.payload)
        await context.checkpoint()
        result = await self.http.post_json(
            self.http.platform_api_url,
            "/internal/v2/exports/render",
            {
                "jobId": str(envelope.job_id),
                **payload.model_dump(mode="json", by_alias=True, exclude={"kind"}),
            },
            max_response_bytes=32_768,
        )
        await context.checkpoint()
        if unavailable := _upstream_unavailable(result):
            return unavailable
        encryption = result.get("encryption")
        base64_value = re.compile(r"^[A-Za-z0-9+/]+={0,2}$")
        if (
            result.get("exportRequestId") != str(payload.export_request_id)
            or result.get("status") != "complete"
            or not isinstance(result.get("artifactId"), str)
            or result.get("mediaType") != "application/vnd.oralsight.export"
            or not isinstance(result.get("sha256"), str)
            or re.fullmatch(r"[a-f0-9]{64}", result["sha256"]) is None
            or not isinstance(result.get("byteSize"), int)
            or not 0 < result["byteSize"] <= 2_147_483_647
            or not isinstance(encryption, dict)
            or encryption.get("scheme") != payload.encryption.scheme
            or any(
                not isinstance(encryption.get(field), str)
                or base64_value.fullmatch(encryption[field]) is None
                for field in (
                    "ephemeralPublicKeyB64",
                    "saltB64",
                    "nonceB64",
                )
            )
        ):
            raise PermanentJobError("invalid_data_export_response")
        return ProcessorResult(
            outcome=JobOutcome.COMPLETE,
            result={"dataExport": result},
        )


@dataclass(slots=True)
class DeleteAllProcessor:
    http: InternalHttpClient

    async def process(
        self, envelope: JobEnvelope, context: JobContext
    ) -> ProcessorResult:
        payload = cast(DeleteAllPayload, envelope.payload)
        await context.checkpoint()
        result = await self.http.post_json(
            self.http.platform_api_url,
            f"/internal/v2/deletion-requests/{payload.deletion_request_id}/execute",
            {
                "jobId": str(envelope.job_id),
                "subjectAccountId": str(payload.subject_account_id),
                "scope": payload.scope,
                "rotateInstallationKey": payload.rotate_installation_key,
            },
        )
        await context.checkpoint()
        if result.get("deletionRequestId") != str(payload.deletion_request_id):
            raise PermanentJobError("invalid_deletion_response")
        if result.get("status") != "complete":
            raise PermanentJobError("incomplete_deletion_response")
        return ProcessorResult(outcome=JobOutcome.COMPLETE, result={"deletion": result})


@dataclass(slots=True)
class ProcessorRegistry:
    processors: dict[JobType, JobProcessor]

    def get(self, job_type: JobType) -> JobProcessor:
        processor = self.processors.get(job_type)
        if processor is None:
            raise PermanentJobError("unsupported_job_type")
        return processor


@dataclass(slots=True)
class PlatformReporter:
    http: InternalHttpClient

    async def report(
        self,
        envelope: JobEnvelope,
        outcome: JobOutcome,
        *,
        result: dict[str, Any] | None = None,
        reason_code: str | None = None,
    ) -> None:
        notification = ResultNotification(
            job_id=envelope.job_id,
            outcome=outcome,
            completed_at=datetime.now(UTC),
            result=result or {},
            reason_code=reason_code,
        )
        await self.http.post_json(
            self.http.platform_api_url,
            f"/internal/v2/jobs/{envelope.job_id}/result",
            notification.model_dump(mode="json", by_alias=True),
        )

    async def register_retention(
        self, envelope: JobEnvelope, outcome: JobOutcome
    ) -> None:
        await self.http.post_json(
            self.http.platform_api_url,
            f"/internal/v2/jobs/{envelope.job_id}/retention",
            {
                "outcome": outcome.value,
                "retention": envelope.retention.model_dump(mode="json", by_alias=True),
            },
        )

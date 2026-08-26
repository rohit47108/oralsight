from __future__ import annotations

import base64
import json
from dataclasses import replace
from pathlib import Path
from types import MappingProxyType

import cv2
import numpy as np
import pytest

from oralsight_api import processing
from oralsight_api.calibration import CalibrationEstimate, NeutralColorReference
from oralsight_api.contracts import (
    AnalysisOrigin,
    AnalysisStatus,
    AnalyzeMetadata,
    CompareMetadata,
    DistributionClass,
    InputOrigin,
    ImagePixelSize,
    ModelHead,
    MouthRegion,
    QualityClass,
    QualityResult,
    RegistrationAlignment,
)
from oralsight_api.model_adapters import (
    AdapterPrediction,
    ClassificationPrediction,
    EmbeddingPrediction,
    ModelAdapterError,
    SegmentationPrediction,
)
from oralsight_api.processing import (
    SanitizedImage,
    analyze_sanitized_image,
    compare_sanitized_images,
)
from oralsight_api.release_manifest import (
    RELEASE_MANIFEST_ENV,
    HeadReleaseState,
    ReleaseRuntimeState,
    empty_release_runtime,
    load_release_runtime,
)


class _FakeAdapter:
    def __init__(
        self,
        head: ModelHead,
        outputs: list[AdapterPrediction | Exception],
    ) -> None:
        self.head = head
        self._outputs = outputs
        self.calls = 0

    def predict(self, _rgb: np.ndarray) -> AdapterPrediction:
        if self.calls >= len(self._outputs):
            raise AssertionError("Fake adapter received too many calls.")
        output = self._outputs[self.calls]
        self.calls += 1
        if isinstance(output, Exception):
            raise output
        return output


def _image() -> SanitizedImage:
    yy, xx = np.mgrid[:64, :64]
    rgb = np.stack(
        (
            (80 + xx * 2) % 256,
            (60 + yy * 2) % 256,
            (40 + xx + yy) % 256,
        ),
        axis=2,
    ).astype(np.uint8)
    return SanitizedImage(
        jpeg_bytes=b"test-only",
        rgb=rgb,
        bgr=cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR),
    )


def _accepted_quality(
    _image: SanitizedImage,
) -> tuple[QualityResult, float]:
    return (
        QualityResult(
            accepted=True,
            blur_score=0.9,
            exposure_score=0.9,
            glare_score=0.05,
            obstruction_score=0.02,
            face_detected=False,
            reasons=[],
        ),
        0.9,
    )


def _runtime(
    adapters: dict[ModelHead, _FakeAdapter],
    *,
    repeated_capture_area_error: float | None = None,
) -> ReleaseRuntimeState:
    empty = empty_release_runtime()
    heads = dict(empty.heads)
    for head in adapters:
        heads[head] = HeadReleaseState(
            head=head,
            enabled=True,
            declared_enabled=True,
            version=f"{head.value}-test-onnx",
            artifact_sha256="a" * 64,
            evaluated_at=None,
            metrics=MappingProxyType({"test_metric": 1.0}),
            unmet_requirements=(),
            reviewer_approved=True,
        )
    return replace(
        empty,
        manifest_loaded=True,
        release_id="test-release",
        heads=MappingProxyType(heads),
        adapters=MappingProxyType(dict(adapters)),
        repeated_capture_area_error=repeated_capture_area_error,
        load_reasons=(),
    )


def _anatomy_prediction(
    region: MouthRegion | None,
    *,
    confidence: float = 0.92,
) -> ClassificationPrediction:
    labels = tuple(item.value for item in MouthRegion)
    probabilities = [1 / len(labels)] * len(labels)
    if region is not None:
        remainder = (1.0 - confidence) / (len(labels) - 1)
        probabilities = [remainder] * len(labels)
        probabilities[labels.index(region.value)] = confidence
    else:
        confidence = max(probabilities)
    return ClassificationPrediction(
        labels=labels,
        probabilities=tuple(probabilities),
        top_label=None if region is None else region.value,
        confidence=confidence,
        abstained=region is None,
    )


def _classification_prediction(
    labels: tuple[str, ...],
    top_label: str,
    *,
    confidence: float = 0.9,
) -> ClassificationPrediction:
    remainder = (1.0 - confidence) / (len(labels) - 1)
    probabilities = [remainder] * len(labels)
    probabilities[labels.index(top_label)] = confidence
    return ClassificationPrediction(
        labels=labels,
        probabilities=tuple(probabilities),
        top_label=top_label,
        confidence=confidence,
        abstained=False,
    )


def _segmentation(
    *,
    x_stop: int = 10,
) -> SegmentationPrediction:
    probabilities = np.full((16, 16), 0.05, dtype=np.float32)
    probabilities[4:12, 4:x_stop] = 0.95
    return SegmentationPrediction(
        probabilities=probabilities,
        threshold=0.5,
        confidence=0.9,
    )


def _analyze_metadata(
    *,
    selected_region: MouthRegion = MouthRegion.LOWER_LIP,
    requested_heads: list[ModelHead] | None = None,
) -> AnalyzeMetadata:
    return AnalyzeMetadata(
        contract_version="1.1.0",
        capture_id="capture-model-test",
        selected_region=selected_region,
        input_origin=InputOrigin.LIVE_CAPTURE,
        requested_heads=requested_heads or [ModelHead.SEGMENTATION, ModelHead.ANATOMY],
    )


def _compare_metadata(
    *,
    with_calibration: bool = False,
    region: MouthRegion = MouthRegion.LOWER_LIP,
) -> CompareMetadata:
    payload: dict[str, object] = {
        "contractVersion": "1.1.0",
        "baselineCaptureId": "baseline-model-test",
        "currentCaptureId": "current-model-test",
        "region": region.value,
        "userConfirmedMatch": True,
        "inputOrigin": "live_capture",
        "baselineAnalysis": {
            "captureId": "baseline-model-test",
            "region": region.value,
            "status": "complete",
            "analysisOrigin": "live_model",
            "qualityAccepted": True,
            "candidateNormalizedArea": 0.1,
            "modelVersions": {"segmentation": "old"},
        },
        "currentAnalysis": {
            "captureId": "current-model-test",
            "region": region.value,
            "status": "complete",
            "analysisOrigin": "live_model",
            "qualityAccepted": True,
            "candidateNormalizedArea": 0.9,
            "modelVersions": {"segmentation": "old"},
        },
    }
    if with_calibration:
        request = {
            "cardVersion": "oralsight-calibration-v1",
            "markerId": 17,
            "markerSideMm": 20,
            "planeConfirmed": True,
        }
        payload["baselineCalibration"] = request
        payload["currentCalibration"] = request
    return CompareMetadata.model_validate(payload)


def test_real_adapter_outputs_complete_primary_analysis_and_mask_descriptors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(processing, "assess_quality", _accepted_quality)
    anatomy = _FakeAdapter(
        ModelHead.ANATOMY,
        [_anatomy_prediction(MouthRegion.LOWER_LIP)],
    )
    segmentation = _FakeAdapter(ModelHead.SEGMENTATION, [_segmentation()])
    runtime = _runtime(
        {
            ModelHead.ANATOMY: anatomy,
            ModelHead.SEGMENTATION: segmentation,
        }
    )

    result = analyze_sanitized_image(_image(), _analyze_metadata(), runtime)

    assert result.status is AnalysisStatus.COMPLETE
    assert result.analysis_origin is AnalysisOrigin.LIVE_MODEL
    assert result.anatomy_prediction.region is MouthRegion.LOWER_LIP
    assert result.anatomy_prediction.selected_region_matches is True
    assert result.candidate_mask is not None
    assert result.descriptors is not None
    assert result.candidate_mask.normalized_area == pytest.approx(
        result.descriptors.normalized_area
    )
    assert result.candidate_mask.normalized_area > 0
    assert result.uncertainty.overall_confidence == pytest.approx(0.9)
    assert result.uncertainty.dataset_similarity is None
    assert result.uncertainty.model_agreement is None
    assert any(
        "no released out-of-distribution model" in limitation
        for limitation in result.uncertainty.limitations
    )
    assert any(
        "no released independent ensemble" in limitation
        for limitation in result.uncertainty.limitations
    )
    assert result.model_versions["segmentation"] == "segmentation-test-onnx"
    assert anatomy.calls == 1
    assert segmentation.calls == 1


def test_analysis_applies_requested_neutral_reference_to_descriptors_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(processing, "assess_quality", _accepted_quality)
    observed: dict[str, object] = {}

    def valid_reference(
        _image_bgr: np.ndarray,
        bounding_box: tuple[float, float, float, float],
        *,
        plane_confirmed: bool,
        expected_marker_id: int,
        marker_side_mm: float,
    ) -> NeutralColorReference:
        observed.update(
            bounding_box=bounding_box,
            plane_confirmed=plane_confirmed,
            expected_marker_id=expected_marker_id,
            marker_side_mm=marker_side_mm,
        )
        return NeutralColorReference(
            card_version="oralsight-calibration-v1",
            marker_id=17,
            applied=True,
            method="neutral-grayscale-patches-affine-rgb-v1",
            rgb_scales=(1.0, 1.0, 1.0),
            rgb_offsets=(0.0, 0.0, 0.0),
            confidence=0.9,
            suppression_reasons=(),
        )

    monkeypatch.setattr(
        processing,
        "estimate_neutral_color_reference",
        valid_reference,
    )
    runtime = _runtime(
        {
            ModelHead.ANATOMY: _FakeAdapter(
                ModelHead.ANATOMY,
                [_anatomy_prediction(MouthRegion.LOWER_LIP)],
            ),
            ModelHead.SEGMENTATION: _FakeAdapter(
                ModelHead.SEGMENTATION,
                [_segmentation()],
            ),
        }
    )
    metadata = AnalyzeMetadata.model_validate(
        {
            "contractVersion": "1.1.0",
            "captureId": "capture-color-reference",
            "selectedRegion": "lower_lip",
            "inputOrigin": "live_capture",
            "requestedHeads": ["segmentation", "anatomy"],
            "calibration": {
                "cardVersion": "oralsight-calibration-v1",
                "markerId": 17,
                "markerSideMm": 20,
                "planeConfirmed": True,
            },
        }
    )

    result = analyze_sanitized_image(_image(), metadata, runtime)

    assert result.status is AnalysisStatus.COMPLETE
    assert observed["plane_confirmed"] is True
    assert observed["expected_marker_id"] == 17
    assert observed["marker_side_mm"] == 20
    assert result.model_versions["descriptor_color_reference"] == (
        "neutral-grayscale-patches-affine-rgb-v1"
    )
    assert any(
        "Mean redness and mean brightness were normalized" in limitation
        for limitation in result.uncertainty.limitations
    )


def test_anatomy_mismatch_prevents_segmentation_and_exposes_no_candidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(processing, "assess_quality", _accepted_quality)
    anatomy = _FakeAdapter(
        ModelHead.ANATOMY,
        [_anatomy_prediction(MouthRegion.UPPER_LIP)],
    )
    segmentation = _FakeAdapter(ModelHead.SEGMENTATION, [_segmentation()])
    result = analyze_sanitized_image(
        _image(),
        _analyze_metadata(selected_region=MouthRegion.LOWER_LIP),
        _runtime(
            {
                ModelHead.ANATOMY: anatomy,
                ModelHead.SEGMENTATION: segmentation,
            }
        ),
    )

    assert result.status is AnalysisStatus.UNSUPPORTED
    assert result.analysis_origin is AnalysisOrigin.LIVE_MODEL
    assert result.candidate_mask is None
    assert "selected_region_anatomy_mismatch" in result.abstention_reasons
    assert segmentation.calls == 0


def test_released_quality_and_distribution_safety_heads_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(processing, "assess_quality", _accepted_quality)
    anatomy = _FakeAdapter(
        ModelHead.ANATOMY,
        [_anatomy_prediction(MouthRegion.LOWER_LIP)],
    )
    quality_labels = tuple(item.value for item in QualityClass)
    runtime = _runtime(
        {
            ModelHead.QUALITY_CONTROL: _FakeAdapter(
                ModelHead.QUALITY_CONTROL,
                [_classification_prediction(quality_labels, QualityClass.TOO_FAR)],
            ),
            ModelHead.ANATOMY: anatomy,
            ModelHead.SEGMENTATION: _FakeAdapter(
                ModelHead.SEGMENTATION, [_segmentation()]
            ),
        }
    )
    result = analyze_sanitized_image(
        _image(),
        _analyze_metadata(
            requested_heads=[
                ModelHead.SEGMENTATION,
                ModelHead.ANATOMY,
                ModelHead.QUALITY_CONTROL,
            ]
        ),
        runtime,
    )
    assert result.status is AnalysisStatus.ABSTAINED
    assert result.quality.accepted is False
    assert "learned_quality_too_far" in result.quality.reasons
    assert anatomy.calls == 0

    distribution_labels = tuple(item.value for item in DistributionClass)
    anatomy = _FakeAdapter(
        ModelHead.ANATOMY,
        [_anatomy_prediction(MouthRegion.LOWER_LIP)],
    )
    runtime = _runtime(
        {
            ModelHead.OUT_OF_DISTRIBUTION: _FakeAdapter(
                ModelHead.OUT_OF_DISTRIBUTION,
                [
                    _classification_prediction(
                        distribution_labels,
                        DistributionClass.UNSUPPORTED,
                    )
                ],
            ),
            ModelHead.ANATOMY: anatomy,
            ModelHead.SEGMENTATION: _FakeAdapter(
                ModelHead.SEGMENTATION, [_segmentation()]
            ),
        }
    )
    result = analyze_sanitized_image(
        _image(),
        _analyze_metadata(
            requested_heads=[
                ModelHead.SEGMENTATION,
                ModelHead.ANATOMY,
                ModelHead.OUT_OF_DISTRIBUTION,
            ]
        ),
        runtime,
    )
    assert result.status is AnalysisStatus.UNSUPPORTED
    assert result.uncertainty.dataset_similarity == pytest.approx(0.1)
    assert "unsupported_image_distribution" in result.abstention_reasons
    assert anatomy.calls == 0


def test_tissue_mask_and_independent_segmentation_agreement_are_applied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(processing, "assess_quality", _accepted_quality)
    tissue = _segmentation(x_stop=8)
    primary = _segmentation(x_stop=12)
    secondary = _segmentation(x_stop=12)
    distribution_labels = tuple(item.value for item in DistributionClass)
    runtime = _runtime(
        {
            ModelHead.ANATOMY: _FakeAdapter(
                ModelHead.ANATOMY,
                [_anatomy_prediction(MouthRegion.LOWER_LIP)],
            ),
            ModelHead.OUT_OF_DISTRIBUTION: _FakeAdapter(
                ModelHead.OUT_OF_DISTRIBUTION,
                [
                    _classification_prediction(
                        distribution_labels,
                        DistributionClass.SUPPORTED,
                    )
                ],
            ),
            ModelHead.ORAL_TISSUE_SEGMENTATION: _FakeAdapter(
                ModelHead.ORAL_TISSUE_SEGMENTATION,
                [tissue],
            ),
            ModelHead.SEGMENTATION: _FakeAdapter(
                ModelHead.SEGMENTATION,
                [primary],
            ),
            ModelHead.SECONDARY_SEGMENTATION: _FakeAdapter(
                ModelHead.SECONDARY_SEGMENTATION,
                [secondary],
            ),
        }
    )
    result = analyze_sanitized_image(
        _image(),
        _analyze_metadata(
            requested_heads=[
                ModelHead.SEGMENTATION,
                ModelHead.ANATOMY,
                ModelHead.ORAL_TISSUE_SEGMENTATION,
                ModelHead.OUT_OF_DISTRIBUTION,
                ModelHead.SECONDARY_SEGMENTATION,
            ]
        ),
        runtime,
    )
    assert result.status is AnalysisStatus.COMPLETE
    assert result.candidate_mask is not None
    assert result.uncertainty.dataset_similarity == pytest.approx(0.9)
    assert result.uncertainty.model_agreement == pytest.approx(1.0)
    assert result.model_versions["oral_tissue_segmentation"]
    assert result.model_versions["secondary_segmentation"]


def test_released_secondary_segmentation_disagreement_withholds_candidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(processing, "assess_quality", _accepted_quality)
    secondary = _segmentation(x_stop=8)
    secondary.probabilities[:, :] = 0.05
    secondary.probabilities[4:12, 10:14] = 0.95
    runtime = _runtime(
        {
            ModelHead.ANATOMY: _FakeAdapter(
                ModelHead.ANATOMY,
                [_anatomy_prediction(MouthRegion.LOWER_LIP)],
            ),
            ModelHead.SEGMENTATION: _FakeAdapter(
                ModelHead.SEGMENTATION,
                [_segmentation(x_stop=8)],
            ),
            ModelHead.SECONDARY_SEGMENTATION: _FakeAdapter(
                ModelHead.SECONDARY_SEGMENTATION,
                [secondary],
            ),
        }
    )
    result = analyze_sanitized_image(
        _image(),
        _analyze_metadata(
            requested_heads=[
                ModelHead.SEGMENTATION,
                ModelHead.ANATOMY,
                ModelHead.SECONDARY_SEGMENTATION,
            ]
        ),
        runtime,
    )
    assert result.status is AnalysisStatus.ABSTAINED
    assert result.candidate_mask is None
    assert result.uncertainty.model_agreement == pytest.approx(0.0)
    assert "segmentation_models_disagree" in result.abstention_reasons


def test_request_time_model_exception_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(processing, "assess_quality", _accepted_quality)
    runtime = _runtime(
        {
            ModelHead.ANATOMY: _FakeAdapter(
                ModelHead.ANATOMY,
                [_anatomy_prediction(MouthRegion.LOWER_LIP)],
            ),
            ModelHead.SEGMENTATION: _FakeAdapter(
                ModelHead.SEGMENTATION,
                [ModelAdapterError("simulated invalid tensor")],
            ),
        }
    )
    result = analyze_sanitized_image(_image(), _analyze_metadata(), runtime)

    assert result.status is AnalysisStatus.ABSTAINED
    assert result.candidate_mask is None
    assert result.descriptors is None
    assert "segmentation_inference_failed" in result.abstention_reasons


def test_optional_classifier_uses_actual_calibrated_adapter_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(processing, "assess_quality", _accepted_quality)
    appearance_labels = (
        "red-patch",
        "white-patch",
        "ulcer-like",
        "mixed",
        "pigmented",
        "none-detected",
        "unsupported",
    )
    appearance = ClassificationPrediction(
        labels=appearance_labels,
        probabilities=(0.8, 0.05, 0.04, 0.03, 0.02, 0.04, 0.02),
        top_label="red-patch",
        confidence=0.8,
        abstained=False,
    )
    runtime = _runtime(
        {
            ModelHead.ANATOMY: _FakeAdapter(
                ModelHead.ANATOMY,
                [_anatomy_prediction(MouthRegion.LOWER_LIP)],
            ),
            ModelHead.SEGMENTATION: _FakeAdapter(
                ModelHead.SEGMENTATION,
                [_segmentation()],
            ),
            ModelHead.APPEARANCE: _FakeAdapter(
                ModelHead.APPEARANCE,
                [appearance],
            ),
        }
    )
    result = analyze_sanitized_image(
        _image(),
        _analyze_metadata(
            requested_heads=[
                ModelHead.SEGMENTATION,
                ModelHead.ANATOMY,
                ModelHead.APPEARANCE,
            ]
        ),
        runtime,
    )

    assert result.status is AnalysisStatus.COMPLETE
    assert result.appearance_output is not None
    assert result.appearance_output.enabled is True
    assert result.appearance_output.top_label == "red-patch"
    assert result.appearance_output.confidence == pytest.approx(0.8)


def test_compare_uses_model_masks_and_embeddings_not_prior_areas(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(processing, "assess_quality", _accepted_quality)
    monkeypatch.setattr(
        processing,
        "_orb_registration",
        lambda _baseline, _current: (
            0.8,
            0.01,
            0.9,
            [],
            np.eye(3, dtype=np.float64),
        ),
    )
    runtime = _runtime(
        {
            ModelHead.SEGMENTATION: _FakeAdapter(
                ModelHead.SEGMENTATION,
                [_segmentation(x_stop=8), _segmentation(x_stop=12)],
            ),
            ModelHead.LESION_REIDENTIFICATION: _FakeAdapter(
                ModelHead.LESION_REIDENTIFICATION,
                [
                    EmbeddingPrediction(
                        values=np.array([1.0, 0.0, 0.0], dtype=np.float32)
                    ),
                    EmbeddingPrediction(
                        values=np.array([1.0, 0.0, 0.0], dtype=np.float32)
                    ),
                ],
            ),
        },
        repeated_capture_area_error=0.08,
    )
    result = compare_sanitized_images(
        _image(),
        _image(),
        _compare_metadata(),
        runtime,
    )

    assert result.comparable is True
    assert result.suppression_reasons == []
    assert result.analysis_origin is AnalysisOrigin.LIVE_MODEL
    assert result.candidate_match_score == pytest.approx(1.0)
    assert result.normalized_change is not None
    assert result.normalized_change > 0
    assert result.descriptor_changes is not None
    assert result.descriptor_changes.normalized_width_change > 0
    assert result.descriptor_changes.normalized_perimeter_change > 0
    assert result.descriptor_changes.measurement_label == (
        "approximate image-normalized change"
    )
    # Caller-provided 0.1 -> 0.9 would imply +800%; the model masks do not.
    assert result.normalized_change < 2


def test_user_confirmed_comparison_does_not_require_automated_reidentification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(processing, "assess_quality", _accepted_quality)
    monkeypatch.setattr(
        processing,
        "_orb_registration",
        lambda _baseline, _current: (
            0.8,
            0.01,
            0.9,
            [],
            np.eye(3, dtype=np.float64),
        ),
    )
    runtime = _runtime(
        {
            ModelHead.SEGMENTATION: _FakeAdapter(
                ModelHead.SEGMENTATION,
                [_segmentation(x_stop=8), _segmentation(x_stop=12)],
            ),
        },
        repeated_capture_area_error=0.08,
    )

    result = compare_sanitized_images(
        _image(),
        _image(),
        _compare_metadata(),
        runtime,
    )

    assert result.candidate_match_score is None
    assert result.comparable is True
    assert result.normalized_change is not None
    assert "lesion_reidentification_release_gate_unmet" not in (
        result.suppression_reasons
    )


def test_user_confirmed_comparison_is_not_suppressed_when_reidentification_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(processing, "assess_quality", _accepted_quality)
    monkeypatch.setattr(
        processing,
        "_orb_registration",
        lambda _baseline, _current: (
            0.8,
            0.01,
            0.9,
            [],
            np.eye(3, dtype=np.float64),
        ),
    )
    runtime = _runtime(
        {
            ModelHead.SEGMENTATION: _FakeAdapter(
                ModelHead.SEGMENTATION,
                [_segmentation(x_stop=8), _segmentation(x_stop=12)],
            ),
            ModelHead.LESION_REIDENTIFICATION: _FakeAdapter(
                ModelHead.LESION_REIDENTIFICATION,
                [ModelAdapterError("simulated embedding failure")],
            ),
        },
        repeated_capture_area_error=0.08,
    )

    result = compare_sanitized_images(
        _image(),
        _image(),
        _compare_metadata(),
        runtime,
    )

    assert result.candidate_match_score is None
    assert result.comparable is True
    assert result.suppression_reasons == []
    assert result.normalized_change is not None


def test_image_relative_change_stays_suppressed_without_repeatability_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(processing, "assess_quality", _accepted_quality)
    monkeypatch.setattr(
        processing,
        "_orb_registration",
        lambda _baseline, _current: (
            0.8,
            0.01,
            0.9,
            [],
            np.eye(3, dtype=np.float64),
        ),
    )
    runtime = _runtime(
        {
            ModelHead.SEGMENTATION: _FakeAdapter(
                ModelHead.SEGMENTATION,
                [_segmentation(x_stop=8), _segmentation(x_stop=12)],
            ),
        },
    )

    result = compare_sanitized_images(
        _image(),
        _image(),
        _compare_metadata(),
        runtime,
    )

    assert result.comparable is False
    assert result.normalized_change is None
    assert result.descriptor_changes is None
    assert result.repeatability_gate_passed is False
    assert result.repeated_capture_area_error is None
    assert "repeated_capture_area_error_gate_unmet" in result.suppression_reasons


def test_physical_change_stays_suppressed_without_repeatability_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(processing, "assess_quality", _accepted_quality)
    monkeypatch.setattr(
        processing,
        "_orb_registration",
        lambda _baseline, _current: (
            0.8,
            0.01,
            0.9,
            [],
            np.eye(3, dtype=np.float64),
        ),
    )

    def calibration_must_not_run(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("Calibration ran without released repeatability evidence.")

    monkeypatch.setattr(
        processing,
        "estimate_calibrated_bounding_box",
        calibration_must_not_run,
    )
    runtime = _runtime(
        {
            ModelHead.SEGMENTATION: _FakeAdapter(
                ModelHead.SEGMENTATION,
                [_segmentation(x_stop=8), _segmentation(x_stop=12)],
            ),
        },
    )

    result = compare_sanitized_images(
        _image(),
        _image(),
        _compare_metadata(with_calibration=True),
        runtime,
    )

    assert result.comparable is False
    assert result.normalized_change is None
    assert result.calibrated_measurement_changes is None
    assert result.calibration_suppression_reasons == [
        "comparison_not_comparable",
        "repeated_capture_area_error_gate_unmet",
    ]


def test_comparison_returns_safe_normalized_current_to_baseline_homography(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(processing, "assess_quality", _accepted_quality)
    # Registration internally maps baseline pixels to current pixels. The
    # public transform is inverted and normalized so a client can align the
    # current capture over the baseline without depending on pixel dimensions.
    baseline_to_current = np.array(
        [
            [1.0, 0.0, 6.3],
            [0.0, 1.0, 12.6],
            [0.0, 0.0, 1.0],
        ],
        dtype=np.float64,
    )
    monkeypatch.setattr(
        processing,
        "_orb_registration",
        lambda _baseline, _current: (
            0.8,
            0.01,
            0.9,
            [],
            baseline_to_current,
        ),
    )
    runtime = _runtime(
        {
            ModelHead.SEGMENTATION: _FakeAdapter(
                ModelHead.SEGMENTATION,
                [_segmentation(), _segmentation()],
            ),
        },
    )

    result = compare_sanitized_images(
        _image(),
        _image(),
        _compare_metadata(),
        runtime,
    )

    alignment = result.registration_alignment
    assert alignment is not None
    assert alignment.method == "orb_ransac_homography"
    assert alignment.coordinate_space == "normalized_image_coordinates"
    assert alignment.maps_from == "current"
    assert alignment.maps_to == "baseline"
    assert alignment.source_image_size.width_px == 64
    assert alignment.source_image_size.height_px == 64
    assert alignment.target_image_size.width_px == 64
    assert alignment.target_image_size.height_px == 64
    assert alignment.matrix == pytest.approx(
        (1.0, 0.0, -0.1, 0.0, 1.0, -0.2, 0.0, 0.0, 1.0)
    )


def test_public_registration_alignment_rejects_extreme_off_canvas_transform() -> None:
    extreme_translation = np.array(
        [
            [1.0, 0.0, 2_000.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
        ],
        dtype=np.float64,
    )

    assert (
        processing._public_registration_alignment(
            _image(),
            _image(),
            extreme_translation,
        )
        is None
    )


def test_registration_alignment_contract_rejects_extreme_finite_transform() -> None:
    with pytest.raises(ValueError, match="safe render range"):
        RegistrationAlignment(
            matrix=(1.0, 0.0, 20.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0),
            source_image_size=ImagePixelSize(width_px=64, height_px=64),
            target_image_size=ImagePixelSize(width_px=64, height_px=64),
        )


def test_packaged_release_runs_live_alignment_but_keeps_change_gate_closed() -> None:
    repository_root = Path(__file__).resolve().parents[3]
    fixture_payload = json.loads(
        (repository_root / "packages/contracts/fixtures/bundled-demo.json").read_text(
            encoding="utf-8"
        )
    )
    image = processing.sanitize_image(base64.b64decode(fixture_payload["base64"]))
    release_manifest = (
        repository_root / "services/inference/release/release-manifest.json"
    )
    runtime = load_release_runtime(
        {RELEASE_MANIFEST_ENV: str(release_manifest.resolve(strict=True))}
    )

    result = compare_sanitized_images(
        image,
        image,
        _compare_metadata(region=MouthRegion.LEFT_BUCCAL_MUCOSA),
        runtime,
    )

    assert ModelHead.SEGMENTATION in runtime.enabled_heads
    assert runtime.repeated_capture_area_error is None
    assert result.analysis_origin is AnalysisOrigin.LIVE_MODEL
    assert result.registration_alignment is not None
    assert result.registration_alignment.matrix == pytest.approx(
        (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0), abs=1e-6
    )
    assert result.registration_alignment.source_image_size.width_px == 160
    assert result.registration_alignment.target_image_size.height_px == 160
    assert result.comparable is False
    assert result.normalized_change is None
    assert result.repeatability_gate_passed is False
    assert result.suppression_reasons == ["repeated_capture_area_error_gate_unmet"]


def test_comparison_normalizes_candidate_area_with_registration_homography(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(processing, "assess_quality", _accepted_quality)
    # The current mask is twice as wide only because the registered tissue is
    # horizontally magnified. Registration maps the baseline mask into the
    # current frame before area change is calculated.
    homography = np.array(
        [
            [2.0, 0.0, -16.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
        ],
        dtype=np.float64,
    )
    monkeypatch.setattr(
        processing,
        "_orb_registration",
        lambda _baseline, _current: (0.9, 0.005, 0.95, [], homography),
    )
    runtime = _runtime(
        {
            ModelHead.SEGMENTATION: _FakeAdapter(
                ModelHead.SEGMENTATION,
                [_segmentation(x_stop=8), _segmentation(x_stop=12)],
            ),
        },
        repeated_capture_area_error=0.08,
    )

    result = compare_sanitized_images(
        _image(),
        _image(),
        _compare_metadata(),
        runtime,
    )

    assert result.comparable is True
    assert result.normalized_change == pytest.approx(0.0, abs=0.08)
    assert result.descriptor_changes is not None
    assert result.descriptor_changes.normalized_width_change == pytest.approx(
        0.0, abs=0.08
    )


def test_comparison_exposes_millimeters_only_after_both_calibrations_pass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(processing, "assess_quality", _accepted_quality)
    monkeypatch.setattr(
        processing,
        "_orb_registration",
        lambda _baseline, _current: (
            0.8,
            0.01,
            0.9,
            [],
            np.eye(3, dtype=np.float64),
        ),
    )
    estimates = iter(
        [
            CalibrationEstimate(
                card_version="oralsight-calibration-v1",
                marker_id=17,
                marker_side_mm=20.0,
                valid=True,
                plane_confirmed=True,
                scale_uncertainty=0.02,
                estimated_width_mm=4.0,
                estimated_height_mm=3.0,
                estimated_area_mm2=12.0,
                confidence=0.9,
                suppression_reasons=(),
            ),
            CalibrationEstimate(
                card_version="oralsight-calibration-v1",
                marker_id=17,
                marker_side_mm=20.0,
                valid=True,
                plane_confirmed=True,
                scale_uncertainty=0.03,
                estimated_width_mm=4.5,
                estimated_height_mm=3.2,
                estimated_area_mm2=14.4,
                confidence=0.88,
                suppression_reasons=(),
            ),
        ]
    )
    monkeypatch.setattr(
        processing,
        "estimate_calibrated_bounding_box",
        lambda *_args, **_kwargs: next(estimates),
    )
    runtime = _runtime(
        {
            ModelHead.SEGMENTATION: _FakeAdapter(
                ModelHead.SEGMENTATION,
                [_segmentation(), _segmentation()],
            ),
        },
        repeated_capture_area_error=0.08,
    )

    result = compare_sanitized_images(
        _image(),
        _image(),
        _compare_metadata(with_calibration=True),
        runtime,
    )

    assert result.comparable is True
    assert result.calibration_suppression_reasons == []
    assert result.calibrated_measurement_changes is not None
    assert result.calibrated_measurement_changes.width_change_mm == pytest.approx(0.5)
    assert result.calibrated_measurement_changes.height_change_mm == pytest.approx(0.2)
    assert result.calibrated_measurement_changes.area_change_mm2 == pytest.approx(2.4)


def test_comparison_suppresses_millimeters_when_either_calibration_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(processing, "assess_quality", _accepted_quality)
    monkeypatch.setattr(
        processing,
        "_orb_registration",
        lambda _baseline, _current: (
            0.8,
            0.01,
            0.9,
            [],
            np.eye(3, dtype=np.float64),
        ),
    )
    valid = CalibrationEstimate(
        card_version="oralsight-calibration-v1",
        marker_id=17,
        marker_side_mm=20.0,
        valid=True,
        plane_confirmed=True,
        scale_uncertainty=0.02,
        estimated_width_mm=4.0,
        estimated_height_mm=3.0,
        estimated_area_mm2=12.0,
        confidence=0.9,
        suppression_reasons=(),
    )
    invalid = CalibrationEstimate(
        card_version="oralsight-calibration-v1",
        marker_id=None,
        marker_side_mm=20.0,
        valid=False,
        plane_confirmed=True,
        scale_uncertainty=None,
        estimated_width_mm=None,
        estimated_height_mm=None,
        estimated_area_mm2=None,
        confidence=0.0,
        suppression_reasons=("calibration_marker_not_found",),
    )
    estimates = iter([valid, invalid])
    monkeypatch.setattr(
        processing,
        "estimate_calibrated_bounding_box",
        lambda *_args, **_kwargs: next(estimates),
    )
    runtime = _runtime(
        {
            ModelHead.SEGMENTATION: _FakeAdapter(
                ModelHead.SEGMENTATION,
                [_segmentation(), _segmentation()],
            ),
        },
        repeated_capture_area_error=0.08,
    )

    result = compare_sanitized_images(
        _image(),
        _image(),
        _compare_metadata(with_calibration=True),
        runtime,
    )

    assert result.comparable is True
    assert result.calibrated_measurement_changes is None
    assert result.calibration_suppression_reasons == [
        "current_calibration_marker_not_found"
    ]

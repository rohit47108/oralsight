"""Exact-hash allowlist and manual outputs for the synthetic bundled demo.

This mirrors ``packages/contracts/fixtures/bundled-demo.json`` so the service
Docker image has no dependency on the monorepo package at runtime.  No fuzzy
matching, filename matching, or caller-supplied identity is trusted.
"""

from __future__ import annotations

from .contracts import (
    AnalysisOrigin,
    AnalysisResult,
    AnalysisStatus,
    AnalyzeMetadata,
    AnatomyPrediction,
    CandidateMask,
    ComparisonResult,
    CompareMetadata,
    DescriptorChanges,
    InputOrigin,
    ModelHead,
    ModelOutput,
    MouthRegion,
    QualityResult,
    Uncertainty,
    VisualDescriptors,
)
from .processing import MODEL_VERSIONS

CANONICAL_DEMO_SHA256 = (
    "61b49da924681f2a8dc6aab6380d7f197483925677af3a4c0a9db63c55a10338"
)
CANONICAL_DEMO_REGION = MouthRegion.LEFT_BUCCAL_MUCOSA


def is_exact_demo_analysis(
    metadata: AnalyzeMetadata,
    actual_sha256: str,
) -> bool:
    return (
        metadata.input_origin is InputOrigin.BUNDLED_DEMO
        and metadata.selected_region is CANONICAL_DEMO_REGION
        and metadata.fixture_sha256 == CANONICAL_DEMO_SHA256
        and actual_sha256 == CANONICAL_DEMO_SHA256
    )


def is_exact_demo_comparison(
    metadata: CompareMetadata,
    baseline_sha256: str,
    current_sha256: str,
) -> bool:
    references = (metadata.baseline_analysis, metadata.current_analysis)
    return (
        metadata.input_origin is InputOrigin.BUNDLED_DEMO
        and metadata.region is CANONICAL_DEMO_REGION
        and baseline_sha256 == CANONICAL_DEMO_SHA256
        and current_sha256 == CANONICAL_DEMO_SHA256
        and all(reference.status is AnalysisStatus.COMPLETE for reference in references)
        and all(
            reference.analysis_origin
            in (AnalysisOrigin.CACHED_MODEL_RESULT, AnalysisOrigin.MANUAL_FIXTURE)
            for reference in references
        )
        and all(reference.quality_accepted for reference in references)
        and all(
            reference.candidate_normalized_area is not None
            and abs(reference.candidate_normalized_area - 0.031) < 1e-9
            for reference in references
        )
        and all(
            reference.model_versions.get("fixture") == "bundled-demo-left-cheek-v1"
            for reference in references
        )
    )


def has_canonical_demo_image_pair(
    metadata: CompareMetadata,
    baseline_sha256: str,
    current_sha256: str,
) -> bool:
    """Identify exact fixture bytes without asserting analysis eligibility."""

    return (
        metadata.input_origin is InputOrigin.BUNDLED_DEMO
        and baseline_sha256 == CANONICAL_DEMO_SHA256
        and current_sha256 == CANONICAL_DEMO_SHA256
    )


def ineligible_demo_comparison(metadata: CompareMetadata) -> ComparisonResult:
    """Fail closed for exact fixture bytes with inconsistent prior metadata.

    An ineligible fixture request must not fall through to live OpenCV/model
    execution: doing so could erase the precise provenance failure behind a
    generic runtime error and would waste CPU on a known fixture.
    """

    reasons: list[str] = []
    if metadata.region is not CANONICAL_DEMO_REGION:
        reasons.append("fixture_region_mismatch")
    for label, reference in (
        ("baseline", metadata.baseline_analysis),
        ("current", metadata.current_analysis),
    ):
        if reference.status is not AnalysisStatus.COMPLETE:
            reasons.append(f"{label}_prior_analysis_not_complete")
        if reference.analysis_origin not in (
            AnalysisOrigin.CACHED_MODEL_RESULT,
            AnalysisOrigin.MANUAL_FIXTURE,
        ):
            reasons.append(f"{label}_prior_analysis_not_verified_fixture")
        if not reference.quality_accepted:
            reasons.append(f"{label}_prior_analysis_quality_rejected")
        if reference.candidate_normalized_area is None:
            reasons.append(f"{label}_prior_candidate_area_unavailable")
        elif abs(reference.candidate_normalized_area - 0.031) >= 1e-9:
            reasons.append(f"{label}_prior_candidate_area_fixture_mismatch")
        if reference.model_versions.get("fixture") != "bundled-demo-left-cheek-v1":
            reasons.append(f"{label}_prior_fixture_version_mismatch")
    if not metadata.user_confirmed_match:
        reasons.append("user_confirmation_required")
    reasons.append("fixture_comparison_not_eligible")

    return ComparisonResult(
        baseline_capture_id=metadata.baseline_capture_id,
        current_capture_id=metadata.current_capture_id,
        region=metadata.region,
        candidate_match_score=None,
        user_confirmed_match=metadata.user_confirmed_match,
        registration_confidence=0,
        inlier_ratio=0,
        reprojection_error_ratio=1,
        normalized_change=None,
        descriptor_changes=None,
        calibrated_measurement_changes=None,
        calibration_suppression_reasons=[],
        comparable=False,
        suppression_reasons=list(dict.fromkeys(reasons)),
        model_versions=MODEL_VERSIONS,
        input_origin=metadata.input_origin,
        analysis_origin=AnalysisOrigin.UNAVAILABLE,
    )


def _gated_output(head_name: str) -> ModelOutput:
    return ModelOutput(
        enabled=False,
        gate_passed=False,
        top_label=None,
        confidence=None,
        scores=[],
        limitation=f"The {head_name} research head remains disabled by its release gate.",
    )


def manual_demo_analysis(metadata: AnalyzeMetadata) -> AnalysisResult:
    appearance = (
        _gated_output("appearance")
        if ModelHead.APPEARANCE in metadata.requested_heads
        else None
    )
    disease = (
        _gated_output("disease-category")
        if ModelHead.DISEASE_RESEARCH in metadata.requested_heads
        else None
    )
    return AnalysisResult(
        capture_id=metadata.capture_id,
        region=metadata.selected_region,
        quality=QualityResult(
            accepted=True,
            blur_score=0.91,
            exposure_score=0.96,
            glare_score=0.02,
            obstruction_score=0.01,
            face_detected=False,
            reasons=[],
        ),
        anatomy_prediction=AnatomyPrediction(
            region=metadata.selected_region,
            confidence=0.82,
            supported=True,
            selected_region_matches=True,
        ),
        candidate_mask=CandidateMask(
            polygon=[
                (0.56, 0.35),
                (0.72, 0.38),
                (0.76, 0.53),
                (0.61, 0.58),
                (0.52, 0.48),
            ],
            bounding_box=(0.52, 0.35, 0.24, 0.23),
            normalized_area=0.031,
        ),
        descriptors=VisualDescriptors(
            normalized_area=0.031,
            perimeter=0.48,
            border_irregularity=0.19,
            mean_redness=0.37,
            mean_brightness=0.58,
            texture_contrast=0.23,
        ),
        appearance_output=appearance,
        disease_research_output=disease,
        uncertainty=Uncertainty(
            overall_confidence=0.78,
            image_quality_confidence=0.92,
            dataset_similarity=0.45,
            model_agreement=0.58,
            limitations=[
                "This manual output is bound to the exact synthetic bundled-demo image hash.",
                "Candidate-region measurements are approximate and non-diagnostic.",
            ],
        ),
        abstention_reasons=[],
        model_versions={**MODEL_VERSIONS, "fixture": "bundled-demo-left-cheek-v1"},
        input_origin=InputOrigin.BUNDLED_DEMO,
        analysis_origin=AnalysisOrigin.MANUAL_FIXTURE,
        status=AnalysisStatus.COMPLETE,
    )


def manual_demo_comparison(metadata: CompareMetadata) -> ComparisonResult:
    reasons: list[str] = []
    if not metadata.user_confirmed_match:
        reasons.append("user_confirmation_required")
    for prefix, prior in (
        ("baseline", metadata.baseline_analysis),
        ("current", metadata.current_analysis),
    ):
        if prior.status is not AnalysisStatus.COMPLETE:
            reasons.append(f"{prefix}_prior_analysis_not_complete")
        if not prior.quality_accepted:
            reasons.append(f"{prefix}_prior_analysis_quality_rejected")
        if prior.candidate_normalized_area is None:
            reasons.append(f"{prefix}_prior_candidate_area_unavailable")

    baseline_area = metadata.baseline_analysis.candidate_normalized_area
    current_area = metadata.current_analysis.candidate_normalized_area
    normalized_change: float | None = None
    if baseline_area is not None and current_area is not None:
        if baseline_area <= 0:
            reasons.append("baseline_candidate_area_zero")
        else:
            normalized_change = (current_area - baseline_area) / baseline_area

    comparable = not reasons
    return ComparisonResult(
        baseline_capture_id=metadata.baseline_capture_id,
        current_capture_id=metadata.current_capture_id,
        region=metadata.region,
        candidate_match_score=1.0,
        user_confirmed_match=metadata.user_confirmed_match,
        registration_confidence=1.0,
        inlier_ratio=1.0,
        reprojection_error_ratio=0.0,
        normalized_change=normalized_change if comparable else None,
        descriptor_changes=(
            DescriptorChanges(
                normalized_width_change=0.0,
                normalized_height_change=0.0,
                normalized_perimeter_change=0.0,
                border_irregularity_change=0.0,
                mean_redness_change=0.0,
                mean_brightness_change=0.0,
                texture_contrast_change=0.0,
                ulceration_like_contrast_change=0.0,
            )
            if comparable
            else None
        ),
        calibrated_measurement_changes=None,
        calibration_suppression_reasons=(
            ["fixture_calibration_not_available"]
            if metadata.baseline_calibration is not None
            or metadata.current_calibration is not None
            else []
        ),
        comparable=comparable,
        suppression_reasons=reasons,
        model_versions={**MODEL_VERSIONS, "fixture": "bundled-demo-left-cheek-v1"},
        input_origin=InputOrigin.BUNDLED_DEMO,
        analysis_origin=AnalysisOrigin.MANUAL_FIXTURE,
    )

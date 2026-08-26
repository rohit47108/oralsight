"""Pydantic mirrors of the public TypeScript contracts.

The canonical contracts live in ``packages/contracts``.  The service mirrors
them so its Docker image remains self-contained; API serialization always uses
the canonical camelCase field names.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

CONTRACT_VERSION = "1.1.0"
DISCLAIMER = "This result is not a diagnosis."


def _to_camel(value: str) -> str:
    first, *rest = value.split("_")
    return first + "".join(part.capitalize() for part in rest)


class ContractModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=_to_camel,
        populate_by_name=True,
        extra="forbid",
        validate_assignment=True,
    )


class MouthRegion(StrEnum):
    DORSAL_TONGUE = "dorsal_tongue"
    VENTRAL_TONGUE = "ventral_tongue"
    LEFT_BUCCAL_MUCOSA = "left_buccal_mucosa"
    RIGHT_BUCCAL_MUCOSA = "right_buccal_mucosa"
    UPPER_LIP = "upper_lip"
    LOWER_LIP = "lower_lip"
    UPPER_DENTAL_ARCH = "upper_dental_arch"
    LOWER_DENTAL_ARCH = "lower_dental_arch"


class InputOrigin(StrEnum):
    LIVE_CAPTURE = "live_capture"
    BUNDLED_DEMO = "bundled_demo"


class AnalysisOrigin(StrEnum):
    LIVE_MODEL = "live_model"
    CACHED_MODEL_RESULT = "cached_model_result"
    MANUAL_FIXTURE = "manual_fixture"
    UNAVAILABLE = "unavailable"


class AnalysisStatus(StrEnum):
    COMPLETE = "complete"
    ABSTAINED = "abstained"
    UNSUPPORTED = "unsupported"
    FAILED = "failed"


class ModelHead(StrEnum):
    SEGMENTATION = "segmentation"
    ANATOMY = "anatomy"
    APPEARANCE = "appearance"
    DISEASE_RESEARCH = "disease_research"
    LESION_REIDENTIFICATION = "lesion_reidentification"
    QUALITY_CONTROL = "quality_control"
    ORAL_TISSUE_SEGMENTATION = "oral_tissue_segmentation"
    OUT_OF_DISTRIBUTION = "out_of_distribution"
    SECONDARY_SEGMENTATION = "secondary_segmentation"


class QualityClass(StrEnum):
    ACCEPTABLE = "acceptable"
    BLURRY = "blurry"
    TOO_DARK = "too-dark"
    TOO_BRIGHT = "too-bright"
    GLARE_HEAVY = "glare-heavy"
    TARGET_REGION_MISSING = "target-region-missing"
    TOO_FAR = "too-far"
    TOO_CLOSE = "too-close"
    OBSTRUCTED = "obstructed"


class DistributionClass(StrEnum):
    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"


class AppearanceClass(StrEnum):
    RED_PATCH = "red-patch"
    WHITE_PATCH = "white-patch"
    ULCER_LIKE = "ulcer-like"
    MIXED = "mixed"
    PIGMENTED = "pigmented"
    NONE_DETECTED = "none-detected"
    UNSUPPORTED = "unsupported"


class DiseaseResearchClass(StrEnum):
    NORMAL = "normal"
    VARIATION = "variation"
    OPMD = "opmd"
    ORAL_CANCER = "oral_cancer"


class AnalysisCalibrationRequest(ContractModel):
    card_version: Literal["oralsight-calibration-v1"]
    marker_id: Literal[17]
    marker_side_mm: Literal[20]
    plane_confirmed: bool


class AnalyzeMetadata(ContractModel):
    contract_version: Literal[CONTRACT_VERSION]
    capture_id: Annotated[str, Field(min_length=1, max_length=128)]
    selected_region: MouthRegion
    input_origin: InputOrigin
    requested_heads: list[ModelHead] = Field(
        default_factory=lambda: [ModelHead.SEGMENTATION, ModelHead.ANATOMY]
    )
    calibration: AnalysisCalibrationRequest | None = None
    fixture_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def fixture_origin_matches_hash(self) -> "AnalyzeMetadata":
        if (
            self.input_origin is InputOrigin.BUNDLED_DEMO
            and self.fixture_sha256 is None
        ):
            raise ValueError(
                "Bundled demonstration input requires its exact fixture hash."
            )
        if (
            self.input_origin is InputOrigin.LIVE_CAPTURE
            and self.fixture_sha256 is not None
        ):
            raise ValueError("Live captures cannot declare a bundled fixture hash.")
        return self


class PriorAnalysisMetadata(ContractModel):
    capture_id: Annotated[str, Field(min_length=1, max_length=128)]
    region: MouthRegion
    status: AnalysisStatus
    analysis_origin: AnalysisOrigin
    quality_accepted: bool
    candidate_normalized_area: Annotated[float, Field(ge=0, le=1)] | None
    model_versions: dict[str, str]


class ComparisonCalibrationRequest(ContractModel):
    card_version: Literal["oralsight-calibration-v1"]
    marker_id: Literal[17]
    marker_side_mm: Literal[20]
    plane_confirmed: Literal[True]


class CompareMetadata(ContractModel):
    contract_version: Literal[CONTRACT_VERSION]
    baseline_capture_id: Annotated[str, Field(min_length=1, max_length=128)]
    current_capture_id: Annotated[str, Field(min_length=1, max_length=128)]
    region: MouthRegion
    user_confirmed_match: bool
    input_origin: InputOrigin
    baseline_analysis: PriorAnalysisMetadata
    current_analysis: PriorAnalysisMetadata
    baseline_calibration: ComparisonCalibrationRequest | None = None
    current_calibration: ComparisonCalibrationRequest | None = None

    @model_validator(mode="after")
    def analysis_references_match_request(self) -> "CompareMetadata":
        if self.baseline_capture_id == self.current_capture_id:
            raise ValueError("A comparison requires two distinct capture IDs.")
        if self.baseline_analysis.capture_id != self.baseline_capture_id:
            raise ValueError("Baseline analysis must belong to the baseline capture.")
        if self.current_analysis.capture_id != self.current_capture_id:
            raise ValueError("Current analysis must belong to the current capture.")
        if self.baseline_analysis.region != self.region:
            raise ValueError("Baseline analysis must use the requested region.")
        if self.current_analysis.region != self.region:
            raise ValueError("Current analysis must use the requested region.")
        return self


class QualityResult(ContractModel):
    accepted: bool
    blur_score: Annotated[
        float, Field(ge=0, le=1, description="Pass score; higher is better.")
    ]
    exposure_score: Annotated[
        float, Field(ge=0, le=1, description="Pass score; higher is better.")
    ]
    glare_score: Annotated[
        float, Field(ge=0, le=1, description="Glare severity; lower is better.")
    ]
    obstruction_score: Annotated[
        float, Field(ge=0, le=1, description="Obstruction severity; lower is better.")
    ]
    face_detected: bool
    reasons: list[str]


class AnatomyPrediction(ContractModel):
    region: MouthRegion | None
    confidence: Annotated[float, Field(ge=0, le=1)]
    supported: bool
    selected_region_matches: bool


NormalizedCoordinate = Annotated[float, Field(ge=0, le=1)]


class CandidateMask(ContractModel):
    polygon: Annotated[
        list[tuple[NormalizedCoordinate, NormalizedCoordinate]], Field(min_length=3)
    ]
    bounding_box: tuple[
        NormalizedCoordinate,
        NormalizedCoordinate,
        NormalizedCoordinate,
        NormalizedCoordinate,
    ]
    normalized_area: Annotated[float, Field(ge=0, le=1)]

    @model_validator(mode="after")
    def normalized_geometry_is_valid(self) -> "CandidateMask":
        x, y, width, height = self.bounding_box
        if width <= 0 or height <= 0 or x + width > 1 + 1e-6 or y + height > 1 + 1e-6:
            raise ValueError(
                "Candidate bounding box must have positive size and stay within normalized bounds."
            )
        return self


class VisualDescriptors(ContractModel):
    normalized_area: Annotated[float, Field(ge=0, le=1)]
    perimeter: Annotated[float, Field(ge=0)]
    border_irregularity: Annotated[float, Field(ge=0)]
    mean_redness: Annotated[float, Field(ge=0, le=1)]
    mean_brightness: Annotated[float, Field(ge=0, le=1)]
    texture_contrast: Annotated[float, Field(ge=0, le=1)]
    measurement_label: Literal["approximate"] = "approximate"


class ClassScore(ContractModel):
    label: Annotated[str, Field(min_length=1)]
    probability: Annotated[float, Field(ge=0, le=1)]


class ModelOutput(ContractModel):
    enabled: bool
    gate_passed: bool
    top_label: Annotated[str, Field(min_length=1)] | None
    confidence: Annotated[float, Field(ge=0, le=1)] | None
    scores: list[ClassScore]
    limitation: Annotated[str, Field(min_length=1)]

    @model_validator(mode="after")
    def predictions_require_an_enabled_gate(self) -> "ModelOutput":
        if self.enabled and not self.gate_passed:
            raise ValueError("A model output cannot be enabled before its gate passes.")
        if not self.enabled and (
            self.top_label is not None or self.confidence is not None or self.scores
        ):
            raise ValueError("A disabled model output cannot expose predictions.")
        return self


class Uncertainty(ContractModel):
    overall_confidence: Annotated[float, Field(ge=0, le=1)]
    image_quality_confidence: Annotated[float, Field(ge=0, le=1)]
    dataset_similarity: Annotated[float, Field(ge=0, le=1)] | None
    model_agreement: Annotated[float, Field(ge=0, le=1)] | None
    limitations: list[str]


class AnalysisResult(ContractModel):
    contract_version: Literal[CONTRACT_VERSION] = CONTRACT_VERSION
    capture_id: Annotated[str, Field(min_length=1)]
    region: MouthRegion
    quality: QualityResult
    anatomy_prediction: AnatomyPrediction
    candidate_mask: CandidateMask | None
    descriptors: VisualDescriptors | None
    appearance_output: ModelOutput | None
    disease_research_output: ModelOutput | None
    uncertainty: Uncertainty
    abstention_reasons: list[str]
    model_versions: dict[str, str]
    input_origin: InputOrigin
    analysis_origin: AnalysisOrigin
    status: AnalysisStatus
    disclaimer: Literal[DISCLAIMER] = DISCLAIMER

    @model_validator(mode="after")
    def analysis_invariants(self) -> "AnalysisResult":
        if (self.candidate_mask is None) != (self.descriptors is None):
            raise ValueError(
                "Candidate masks and descriptors must be present together."
            )
        if (
            self.candidate_mask is not None
            and self.descriptors is not None
            and abs(
                self.candidate_mask.normalized_area - self.descriptors.normalized_area
            )
            > 1e-6
        ):
            raise ValueError("Candidate mask and descriptor area must match.")
        if self.quality.face_detected and self.quality.accepted:
            raise ValueError("A face-containing capture cannot be quality accepted.")
        if self.status is AnalysisStatus.COMPLETE and (
            not self.quality.accepted
            or not self.anatomy_prediction.supported
            or not self.anatomy_prediction.selected_region_matches
        ):
            raise ValueError(
                "Complete analysis requires accepted quality and matching supported anatomy."
            )
        if self.status is not AnalysisStatus.COMPLETE and (
            self.candidate_mask is not None or self.descriptors is not None
        ):
            raise ValueError("Non-complete analysis cannot expose a candidate result.")
        if (
            self.analysis_origin
            in {
                AnalysisOrigin.CACHED_MODEL_RESULT,
                AnalysisOrigin.MANUAL_FIXTURE,
            }
            and self.input_origin is not InputOrigin.BUNDLED_DEMO
        ):
            raise ValueError(
                "Fixture or cached output is valid only for bundled input."
            )

        allowed_by_output = (
            (
                self.appearance_output,
                {item.value for item in AppearanceClass},
                "appearanceOutput",
            ),
            (
                self.disease_research_output,
                {item.value for item in DiseaseResearchClass},
                "diseaseResearchOutput",
            ),
        )
        for output, allowed, label in allowed_by_output:
            if output is None:
                continue
            labels = [score.label for score in output.scores]
            if output.top_label is not None:
                labels.append(output.top_label)
            if any(value not in allowed for value in labels):
                raise ValueError(
                    f"{label} contains a label outside its fixed taxonomy."
                )
        return self


class DescriptorChanges(ContractModel):
    normalized_width_change: Annotated[float, Field(ge=-1)]
    normalized_height_change: Annotated[float, Field(ge=-1)]
    normalized_perimeter_change: Annotated[float, Field(ge=-1)]
    border_irregularity_change: float
    mean_redness_change: Annotated[float, Field(ge=-1, le=1)]
    mean_brightness_change: Annotated[float, Field(ge=-1, le=1)]
    texture_contrast_change: Annotated[float, Field(ge=-1, le=1)]
    ulceration_like_contrast_change: Annotated[float, Field(ge=-1, le=1)] | None
    measurement_label: Literal["approximate image-normalized change"] = (
        "approximate image-normalized change"
    )


class CalibratedMeasurementChanges(ContractModel):
    card_version: Literal["oralsight-calibration-v1"]
    marker_id: Literal[17]
    marker_side_mm: Literal[20]
    baseline_width_mm: Annotated[float, Field(gt=0)]
    current_width_mm: Annotated[float, Field(gt=0)]
    width_change_mm: float
    baseline_height_mm: Annotated[float, Field(gt=0)]
    current_height_mm: Annotated[float, Field(gt=0)]
    height_change_mm: float
    baseline_area_mm2: Annotated[float, Field(gt=0)]
    current_area_mm2: Annotated[float, Field(gt=0)]
    area_change_mm2: float
    baseline_confidence: Annotated[float, Field(ge=0, le=1)]
    current_confidence: Annotated[float, Field(ge=0, le=1)]
    measurement_label: Literal["calibrated estimate"] = "calibrated estimate"


class ImagePixelSize(ContractModel):
    width_px: Annotated[int, Field(ge=1, le=2048)]
    height_px: Annotated[int, Field(ge=1, le=2048)]


class RegistrationAlignment(ContractModel):
    method: Literal["orb_ransac_homography"] = "orb_ransac_homography"
    coordinate_space: Literal["normalized_image_coordinates"] = (
        "normalized_image_coordinates"
    )
    maps_from: Literal["current"] = "current"
    maps_to: Literal["baseline"] = "baseline"
    matrix: tuple[
        float,
        float,
        float,
        float,
        float,
        float,
        float,
        float,
        float,
    ]
    source_image_size: ImagePixelSize
    target_image_size: ImagePixelSize

    @model_validator(mode="after")
    def matrix_is_safe_to_render(self) -> "RegistrationAlignment":
        if not all(math.isfinite(value) for value in self.matrix):
            raise ValueError("Registration alignment matrix must be finite.")
        if not math.isclose(self.matrix[8], 1.0, abs_tol=1e-6):
            raise ValueError("Registration alignment matrix must be normalized.")
        determinant = (
            self.matrix[0]
            * (self.matrix[4] * self.matrix[8] - self.matrix[5] * self.matrix[7])
            - self.matrix[1]
            * (self.matrix[3] * self.matrix[8] - self.matrix[5] * self.matrix[6])
            + self.matrix[2]
            * (self.matrix[3] * self.matrix[7] - self.matrix[4] * self.matrix[6])
        )
        if not math.isfinite(determinant) or abs(determinant) < 1e-10:
            raise ValueError("Registration alignment matrix must be invertible.")
        for x_value in (0.0, 0.5, 1.0):
            for y_value in (0.0, 0.5, 1.0):
                denominator = (
                    self.matrix[6] * x_value + self.matrix[7] * y_value + self.matrix[8]
                )
                if abs(denominator) < 1e-6:
                    raise ValueError(
                        "Registration alignment has an unsafe projective horizon."
                    )
                projected_x = (
                    self.matrix[0] * x_value + self.matrix[1] * y_value + self.matrix[2]
                ) / denominator
                projected_y = (
                    self.matrix[3] * x_value + self.matrix[4] * y_value + self.matrix[5]
                ) / denominator
                if (
                    not math.isfinite(projected_x)
                    or not math.isfinite(projected_y)
                    or max(abs(projected_x), abs(projected_y)) > 16.0
                ):
                    raise ValueError(
                        "Registration alignment projects outside the safe render range."
                    )
        return self


class ComparisonResult(ContractModel):
    contract_version: Literal[CONTRACT_VERSION] = CONTRACT_VERSION
    baseline_capture_id: Annotated[str, Field(min_length=1)]
    current_capture_id: Annotated[str, Field(min_length=1)]
    region: MouthRegion
    candidate_match_score: Annotated[float, Field(ge=0, le=1)] | None
    user_confirmed_match: bool
    registration_confidence: Annotated[float, Field(ge=0, le=1)]
    inlier_ratio: Annotated[float, Field(ge=0, le=1)]
    reprojection_error_ratio: Annotated[float, Field(ge=0)]
    repeated_capture_area_error: Annotated[float, Field(ge=0, le=0.1)] | None = None
    repeatability_gate_passed: bool = False
    registration_alignment: RegistrationAlignment | None = None
    normalized_change: Annotated[float, Field(ge=-1)] | None
    descriptor_changes: DescriptorChanges | None = None
    calibrated_measurement_changes: CalibratedMeasurementChanges | None = None
    calibration_suppression_reasons: list[str] = Field(default_factory=list)
    comparable: bool
    suppression_reasons: list[str]
    model_versions: dict[str, str]
    input_origin: InputOrigin
    analysis_origin: AnalysisOrigin
    disclaimer: Literal[DISCLAIMER] = DISCLAIMER

    @model_validator(mode="after")
    def comparison_invariants(self) -> "ComparisonResult":
        if self.repeatability_gate_passed != (
            self.repeated_capture_area_error is not None
        ):
            raise ValueError(
                "Repeatability gate status requires matching released evidence."
            )
        if (
            self.calibrated_measurement_changes is not None
            and not self.repeatability_gate_passed
        ):
            raise ValueError(
                "Calibrated physical change requires released repeatability evidence."
            )
        if self.registration_alignment is not None and (
            self.inlier_ratio < 0.60
            or self.reprojection_error_ratio > 0.03
            or self.analysis_origin is not AnalysisOrigin.LIVE_MODEL
        ):
            raise ValueError(
                "Registration alignment requires a gated live-model homography."
            )
        if self.comparable and (
            not self.user_confirmed_match
            or not self.repeatability_gate_passed
            or self.normalized_change is None
            or self.inlier_ratio < 0.60
            or self.reprojection_error_ratio > 0.03
            or self.suppression_reasons
        ):
            raise ValueError(
                "Comparable change requires confirmation and every registration gate."
            )
        if not self.comparable and self.normalized_change is not None:
            raise ValueError("Suppressed comparison cannot expose normalized change.")
        if not self.comparable and (
            self.descriptor_changes is not None
            or self.calibrated_measurement_changes is not None
        ):
            raise ValueError(
                "Suppressed comparison cannot expose descriptor or calibrated change."
            )
        if (
            self.analysis_origin
            in {
                AnalysisOrigin.CACHED_MODEL_RESULT,
                AnalysisOrigin.MANUAL_FIXTURE,
            }
            and self.input_origin is not InputOrigin.BUNDLED_DEMO
        ):
            raise ValueError(
                "Fixture or cached output is valid only for bundled input."
            )
        return self


class ReleaseGate(ContractModel):
    head: ModelHead
    passed: bool
    evaluated_at: datetime | None
    metrics: dict[str, float]
    unmet_requirements: list[str]
    reviewer_approved: bool

    @field_validator("evaluated_at")
    @classmethod
    def evaluated_at_must_be_utc(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("evaluatedAt must include the UTC timezone.")
        if value.utcoffset() != timedelta(0):
            raise ValueError(
                "evaluatedAt must use UTC so contract serialization ends in Z."
            )
        return value.astimezone(timezone.utc)

    @field_serializer("evaluated_at", when_used="json")
    def serialize_evaluated_at(self, value: datetime | None) -> str | None:
        return value.isoformat().replace("+00:00", "Z") if value else None


class ModelCard(ContractModel):
    contract_version: Literal[CONTRACT_VERSION] = CONTRACT_VERSION
    service_version: Annotated[str, Field(min_length=1)]
    intended_use: Annotated[str, Field(min_length=1)]
    forbidden_claims: list[str]
    model_versions: dict[str, str]
    artifact_hashes: dict[str, Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")] | None]
    enabled_heads: list[ModelHead]
    release_gates: list[ReleaseGate]
    comparison_repeated_capture_area_error: (
        Annotated[float, Field(ge=0, le=0.1)] | None
    ) = None
    comparison_repeatability_gate_passed: bool = False
    limitations: list[str]
    disclaimer: Literal[DISCLAIMER] = DISCLAIMER

    @model_validator(mode="after")
    def enabled_heads_have_release_evidence(self) -> "ModelCard":
        if self.comparison_repeatability_gate_passed != (
            self.comparison_repeated_capture_area_error is not None
        ):
            raise ValueError(
                "Comparison repeatability status requires matching released evidence."
            )
        gates = {gate.head: gate for gate in self.release_gates}
        for head in self.enabled_heads:
            gate = gates.get(head)
            if gate is None or not gate.passed:
                raise ValueError("Every enabled head requires a passed release gate.")
            if (
                gate.evaluated_at is None
                or not gate.metrics
                or gate.unmet_requirements
                or not gate.reviewer_approved
            ):
                raise ValueError(
                    "Enabled heads require dated metrics, no unmet requirements, and review approval."
                )
            artifact_name = {
                ModelHead.SEGMENTATION: "segmentation_weights",
                ModelHead.ANATOMY: "anatomy_weights",
                ModelHead.APPEARANCE: "appearance_weights",
                ModelHead.DISEASE_RESEARCH: "disease_research_weights",
                ModelHead.LESION_REIDENTIFICATION: "lesion_reidentification_weights",
                ModelHead.QUALITY_CONTROL: "quality_control_weights",
                ModelHead.ORAL_TISSUE_SEGMENTATION: "oral_tissue_segmentation_weights",
                ModelHead.OUT_OF_DISTRIBUTION: "out_of_distribution_weights",
                ModelHead.SECONDARY_SEGMENTATION: "secondary_segmentation_weights",
            }[head]
            if self.artifact_hashes.get(artifact_name) is None:
                raise ValueError("Enabled heads require a pinned weight artifact hash.")
        return self


class ApiErrorDetail(ContractModel):
    code: Annotated[str, Field(min_length=1)]
    message: Annotated[str, Field(min_length=1)]
    request_id: Annotated[str, Field(min_length=1)]


class ApiError(ContractModel):
    error: ApiErrorDetail

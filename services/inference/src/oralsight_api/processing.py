"""Image sanitization, quality checks, learned inference, and registration.

Learned outputs are available only through startup-validated, hash-pinned ONNX
adapters. The deterministic routines here derive visual descriptors from an
actual model mask; they do not substitute color rules for a missing model.
"""

from __future__ import annotations

import io
import hashlib
import math
import threading
import warnings
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

from .contracts import (
    AnalysisOrigin,
    AnalysisResult,
    AnalysisStatus,
    AnalyzeMetadata,
    AnatomyPrediction,
    AppearanceClass,
    CandidateMask,
    ClassScore,
    ComparisonResult,
    CompareMetadata,
    DiseaseResearchClass,
    ModelHead,
    ModelOutput,
    MouthRegion,
    QualityResult,
    Uncertainty,
    VisualDescriptors,
)
from .model_adapters import (
    ClassificationPrediction,
    EmbeddingPrediction,
    ModelAdapter,
    ModelAdapterError,
    SegmentationPrediction,
)
from .release_manifest import RELEASE_RUNTIME, ReleaseRuntimeState

MAX_IMAGE_BYTES = 1_750_000
MAX_IMAGE_PIXELS = 20_000_000
MAX_PROCESSING_EDGE = 2_048
SUPPORTED_MEDIA_TYPES = {"image/jpeg", "image/png", "image/webp"}
SUPPORTED_PIL_FORMATS = {"JPEG", "PNG", "WEBP"}

MODEL_VERSIONS = {
    "quality": "opencv-quality-yunet-v3",
    "registration": "orb-homography-area-normalization-v2",
}
YUNET_MODEL_PATH = (
    Path(__file__).resolve().parent / "assets" / "face_detection_yunet_2023mar.onnx"
)
YUNET_MODEL_SHA256 = "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4"
# Calibrated on licensed SMART-OM train/validation images and deliberately
# blurred copies. The prior 0.09 cutoff rejected roughly 31% of the usable
# calibration images; this cutoff rejected 9.2% while accepting none of the
# severe-blur controls. Physical-device acceptance testing remains a release
# requirement.
MIN_BLUR_SCORE = 0.054


class ImageInputError(ValueError):
    """Raised when bytes cannot safely be treated as a supported image."""


@dataclass(frozen=True, slots=True)
class SanitizedImage:
    """An EXIF-free JPEG and the exact pixels used for analysis."""

    jpeg_bytes: bytes
    rgb: np.ndarray
    bgr: np.ndarray


def _clamp(value: float) -> float:
    return float(max(0.0, min(1.0, value)))


def _invoked_model_versions(
    runtime: ReleaseRuntimeState,
    invoked_heads: set[ModelHead],
) -> dict[str, str]:
    versions = dict(MODEL_VERSIONS)
    for head in invoked_heads:
        state = runtime.heads[head]
        if state.version is not None:
            versions[head.value] = state.version
    return versions


def sanitize_image(raw: bytes) -> SanitizedImage:
    """Decode, orient, bound, RGB-normalize, and re-encode an upload.

    Processing the re-decoded JPEG ensures descriptors correspond to the
    sanitized bytes that could safely be forwarded to a model.  No EXIF,
    filename, ICC profile, or other source metadata survives this boundary.
    """

    if not raw:
        raise ImageInputError("The uploaded image is empty.")
    if len(raw) > MAX_IMAGE_BYTES:
        raise ImageInputError("The uploaded image exceeds the 1.75 MB transport limit.")

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as source:
                source_format = (source.format or "").upper()
                if source_format not in SUPPORTED_PIL_FORMATS:
                    raise ImageInputError(
                        "Only JPEG, PNG, and WebP images are supported."
                    )
                if getattr(source, "n_frames", 1) != 1:
                    raise ImageInputError(
                        "Animated or multi-frame images are not supported."
                    )
                width, height = source.size
                if width < 1 or height < 1 or width * height > MAX_IMAGE_PIXELS:
                    raise ImageInputError("The image dimensions are not supported.")
                oriented = ImageOps.exif_transpose(source)
                rgb_image = oriented.convert("RGB")
                if max(rgb_image.size) > MAX_PROCESSING_EDGE:
                    rgb_image.thumbnail(
                        (MAX_PROCESSING_EDGE, MAX_PROCESSING_EDGE),
                        Image.Resampling.LANCZOS,
                    )

                encoded = io.BytesIO()
                rgb_image.save(
                    encoded,
                    format="JPEG",
                    quality=90,
                    optimize=False,
                    progressive=False,
                    exif=b"",
                )
    except ImageInputError:
        raise
    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        Image.DecompressionBombError,
    ) as exc:
        raise ImageInputError("The upload is not a decodable image.") from exc
    except Image.DecompressionBombWarning as exc:
        raise ImageInputError("The image dimensions exceed the safety limit.") from exc

    jpeg_bytes = encoded.getvalue()
    encoded_array = np.frombuffer(jpeg_bytes, dtype=np.uint8)
    bgr = cv2.imdecode(encoded_array, cv2.IMREAD_COLOR)
    if bgr is None:
        raise ImageInputError("The sanitized image could not be decoded.")
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    return SanitizedImage(jpeg_bytes=jpeg_bytes, rgb=rgb, bgr=bgr)


@dataclass(frozen=True, slots=True)
class _FaceDetectorState:
    detector: object
    lock: threading.Lock


@lru_cache(maxsize=1)
def _face_detector() -> _FaceDetectorState | None:
    try:
        if (
            not YUNET_MODEL_PATH.is_file()
            or hashlib.sha256(YUNET_MODEL_PATH.read_bytes()).hexdigest()
            != YUNET_MODEL_SHA256
        ):
            return None
        detector = cv2.FaceDetectorYN_create(
            str(YUNET_MODEL_PATH),
            "",
            (320, 320),
            0.85,
            0.3,
            5000,
        )
        return _FaceDetectorState(
            detector=detector,
            lock=threading.Lock(),
        )
    except (AttributeError, cv2.error, OSError, ValueError):
        return None


def _detect_face(image: SanitizedImage) -> bool | None:
    state = _face_detector()
    if state is None:
        return None
    height, width = image.bgr.shape[:2]
    longest = max(height, width)
    scale = min(1.0, 640.0 / max(longest, 1))
    detection_image = (
        image.bgr
        if scale == 1.0
        else cv2.resize(
            image.bgr,
            (max(1, round(width * scale)), max(1, round(height * scale))),
            interpolation=cv2.INTER_AREA,
        )
    )
    detection_height, detection_width = detection_image.shape[:2]
    try:
        with state.lock:
            state.detector.setInputSize((detection_width, detection_height))
            _, faces = state.detector.detect(detection_image)
    except (AttributeError, cv2.error, TypeError, ValueError):
        return None
    return faces is not None and len(faces) > 0


def assess_quality(image: SanitizedImage) -> tuple[QualityResult, float]:
    """Return deterministic, normalized capture-quality signals.

    ``blurScore`` and ``exposureScore`` are pass confidences (higher is better),
    while ``glareScore`` and ``obstructionScore`` are problem severities (lower
    is better).  The API README records these semantics for clients.
    """

    gray = cv2.cvtColor(image.bgr, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(image.bgr, cv2.COLOR_BGR2HSV)
    height, width = gray.shape

    laplacian_variance = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    blur_score = _clamp(1.0 - math.exp(-laplacian_variance / 180.0))
    exposure_score = _clamp(float(np.mean((gray >= 30) & (gray <= 225))))
    glare_score = _clamp(float(np.mean((hsv[:, :, 2] >= 245) & (hsv[:, :, 1] <= 55))))
    obstruction_score = _clamp(float(np.mean(gray <= 20)))

    face_check = _detect_face(image) if min(width, height) >= 128 else None
    face_detected = face_check is True

    reasons: list[str] = []
    if min(width, height) < 128:
        reasons.append("image_too_small")
    if blur_score < MIN_BLUR_SCORE:
        reasons.append("image_too_blurry")
    if exposure_score < 0.65:
        reasons.append("exposure_out_of_range")
    if glare_score > 0.15:
        reasons.append("excessive_glare")
    if obstruction_score > 0.20:
        reasons.append("image_obstructed")
    if face_detected:
        reasons.append("face_detected")
    elif face_check is None:
        reasons.append("face_check_unavailable")

    quality_confidence = _clamp(
        np.mean(
            [
                blur_score,
                exposure_score,
                1.0 - glare_score,
                1.0 - obstruction_score,
            ]
        )
        * (0.5 if face_detected else 1.0)
    )
    return (
        QualityResult(
            accepted=not reasons,
            blur_score=blur_score,
            exposure_score=exposure_score,
            glare_score=glare_score,
            obstruction_score=obstruction_score,
            face_detected=face_detected,
            reasons=reasons,
        ),
        quality_confidence,
    )


def candidate_from_model_mask(
    image: SanitizedImage,
    prediction: SegmentationPrediction,
) -> tuple[CandidateMask | None, VisualDescriptors | None, np.ndarray | None]:
    """Convert one validated model probability map into approximate descriptors."""

    probabilities = np.asarray(prediction.probabilities, dtype=np.float32)
    if (
        probabilities.ndim != 2
        or probabilities.size == 0
        or not np.all(np.isfinite(probabilities))
        or float(np.min(probabilities)) < 0
        or float(np.max(probabilities)) > 1
        or not math.isfinite(prediction.threshold)
        or not 0 < prediction.threshold < 1
        or not math.isfinite(prediction.confidence)
        or not 0 <= prediction.confidence <= 1
    ):
        raise ModelAdapterError("Segmentation probability map is invalid.")

    rgb = image.rgb
    height, width, _ = rgb.shape
    resized_probabilities = cv2.resize(
        probabilities,
        (width, height),
        interpolation=cv2.INTER_LINEAR,
    )
    binary = (resized_probabilities >= prediction.threshold).astype(np.uint8) * 255

    count, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    image_area = width * height
    candidates: list[tuple[int, int]] = []
    for label in range(1, count):
        component_area = int(stats[label, cv2.CC_STAT_AREA])
        area_ratio = component_area / image_area
        if 0 < area_ratio <= 1:
            candidates.append((component_area, label))
    if not candidates:
        return None, None, None

    component_area, best_label = max(candidates)
    component = (labels == best_label).astype(np.uint8) * 255
    contours, _ = cv2.findContours(
        component, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    if not contours:
        return None, None, None
    contour = max(contours, key=cv2.contourArea)
    geometric_area = float(cv2.contourArea(contour))
    if geometric_area <= 0:
        return None, None, None

    perimeter_pixels = float(cv2.arcLength(contour, True))
    approximated = cv2.approxPolyDP(contour, max(1.0, perimeter_pixels * 0.015), True)
    points = approximated.reshape(-1, 2)
    x, y, box_width, box_height = cv2.boundingRect(contour)
    if len(points) < 3:
        points = np.array(
            [
                [x, y],
                [x + box_width - 1, y],
                [x + box_width - 1, y + box_height - 1],
                [x, y + box_height - 1],
            ],
            dtype=np.int32,
        )

    x_divisor = max(width - 1, 1)
    y_divisor = max(height - 1, 1)
    polygon = [
        (_clamp(float(point_x) / x_divisor), _clamp(float(point_y) / y_divisor))
        for point_x, point_y in points
    ]
    normalized_area = _clamp(component_area / image_area)
    bounding_box = (
        _clamp(x / width),
        _clamp(y / height),
        _clamp(box_width / width),
        _clamp(box_height / height),
    )

    mask_pixels = component.astype(bool)
    rgb_float = rgb.astype(np.float32)
    selected_rgb = rgb_float[mask_pixels]
    mean_redness = _clamp(
        float(
            np.mean(
                np.maximum(
                    0.0,
                    selected_rgb[:, 0]
                    - (selected_rgb[:, 1] + selected_rgb[:, 2]) / 2.0,
                )
            )
            / 255.0
        )
    )
    mean_brightness = _clamp(float(np.mean(selected_rgb)) / 255.0)
    gray = cv2.cvtColor(image.bgr, cv2.COLOR_BGR2GRAY)
    texture_values = cv2.Laplacian(gray, cv2.CV_32F)[mask_pixels]
    texture_contrast = _clamp(float(np.std(texture_values)) / 64.0)
    border_irregularity = max(
        0.0,
        (perimeter_pixels * perimeter_pixels) / (4.0 * math.pi * geometric_area) - 1.0,
    )

    candidate = CandidateMask(
        polygon=polygon,
        bounding_box=bounding_box,
        normalized_area=normalized_area,
    )
    descriptors = VisualDescriptors(
        normalized_area=normalized_area,
        perimeter=perimeter_pixels / max(math.hypot(width, height), 1.0),
        border_irregularity=border_irregularity,
        mean_redness=mean_redness,
        mean_brightness=mean_brightness,
        texture_contrast=texture_contrast,
    )
    return candidate, descriptors, component


def _gated_output(head_name: str) -> ModelOutput:
    return ModelOutput(
        enabled=False,
        gate_passed=False,
        top_label=None,
        confidence=None,
        scores=[],
        limitation=(
            f"The {head_name} research head is disabled because its release gate "
            "has not been satisfied and clinically reviewed."
        ),
    )


def _abstained_model_output(head_name: str, limitation: str) -> ModelOutput:
    return ModelOutput(
        enabled=True,
        gate_passed=True,
        top_label=None,
        confidence=None,
        scores=[],
        limitation=f"The {head_name} research head {limitation}",
    )


def _classification_model_output(
    adapter: ModelAdapter,
    image: SanitizedImage,
    *,
    head_name: str,
    expected_labels: tuple[str, ...],
) -> ModelOutput:
    prediction = adapter.predict(image.rgb)
    if not isinstance(prediction, ClassificationPrediction):
        raise ModelAdapterError(
            f"The {head_name} adapter returned the wrong output type."
        )
    _validate_classification_prediction(prediction, expected_labels)
    return ModelOutput(
        enabled=True,
        gate_passed=True,
        top_label=prediction.top_label,
        confidence=prediction.confidence,
        scores=(
            []
            if prediction.abstained
            else [
                ClassScore(label=label, probability=probability)
                for label, probability in zip(
                    prediction.labels,
                    prediction.probabilities,
                    strict=True,
                )
            ]
        ),
        limitation=(
            f"The {head_name} result is a gated experimental research output, "
            "not a diagnosis or care recommendation."
            if not prediction.abstained
            else (
                f"The {head_name} model abstained because calibrated confidence "
                "was below its release threshold."
            )
        ),
    )


def _validate_classification_prediction(
    prediction: ClassificationPrediction,
    expected_labels: tuple[str, ...],
) -> None:
    probabilities = np.asarray(prediction.probabilities, dtype=np.float64)
    if (
        prediction.labels != expected_labels
        or probabilities.shape != (len(expected_labels),)
        or not np.all(np.isfinite(probabilities))
        or np.any(probabilities < 0)
        or np.any(probabilities > 1)
        or not math.isclose(float(np.sum(probabilities)), 1.0, abs_tol=1e-6)
        or not math.isfinite(prediction.confidence)
        or not 0 <= prediction.confidence <= 1
    ):
        raise ModelAdapterError("Classification probabilities are invalid.")
    top_index = int(np.argmax(probabilities))
    if not math.isclose(
        prediction.confidence,
        float(probabilities[top_index]),
        abs_tol=1e-6,
    ):
        raise ModelAdapterError("Classification confidence is inconsistent.")
    expected_top_label = expected_labels[top_index]
    if prediction.abstained:
        if prediction.top_label is not None:
            raise ModelAdapterError("An abstained classification exposed a label.")
    elif prediction.top_label != expected_top_label:
        raise ModelAdapterError("Classification top label is inconsistent.")


def analyze_sanitized_image(
    image: SanitizedImage,
    metadata: AnalyzeMetadata,
    runtime: ReleaseRuntimeState | None = None,
) -> AnalysisResult:
    runtime = RELEASE_RUNTIME if runtime is None else runtime
    quality, quality_confidence = assess_quality(image)
    requested = set(metadata.requested_heads)
    anatomy_prediction = AnatomyPrediction(
        region=None,
        confidence=0.0,
        supported=False,
        selected_region_matches=False,
    )
    abstention_reasons = list(quality.reasons)
    limitations = [
        "All candidate areas and visual descriptors are approximate and have no physical scale.",
        "Model outputs are research observations and cannot diagnose or rule out disease.",
        (
            "Dataset similarity was not assessed because no released "
            "out-of-distribution model is available."
        ),
        (
            "Model agreement was not assessed because no released independent "
            "ensemble is available."
        ),
    ]
    successful_model_output = False
    invoked_heads: set[ModelHead] = set()
    anatomy_supported_and_matches = False
    segmentation_prediction: SegmentationPrediction | None = None
    segmentation_confidence = 0.0

    for required_head in (ModelHead.SEGMENTATION, ModelHead.ANATOMY):
        if (
            not runtime.heads[required_head].enabled
            or required_head not in runtime.adapters
        ):
            abstention_reasons.append(f"{required_head.value}_release_gate_unmet")
    abstention_reasons.extend(runtime.load_reasons)

    anatomy_adapter = runtime.adapters.get(ModelHead.ANATOMY)
    if quality.accepted and anatomy_adapter is not None:
        invoked_heads.add(ModelHead.ANATOMY)
        try:
            anatomy_result = anatomy_adapter.predict(image.rgb)
            if not isinstance(anatomy_result, ClassificationPrediction):
                raise ModelAdapterError(
                    "The anatomy adapter returned the wrong output type."
                )
            expected_labels = tuple(region.value for region in MouthRegion)
            _validate_classification_prediction(anatomy_result, expected_labels)
            predicted_region = (
                MouthRegion(anatomy_result.top_label)
                if anatomy_result.top_label is not None
                else None
            )
            successful_model_output = True
            anatomy_supported_and_matches = predicted_region is metadata.selected_region
            anatomy_prediction = AnatomyPrediction(
                region=predicted_region,
                confidence=anatomy_result.confidence,
                supported=predicted_region is not None,
                selected_region_matches=anatomy_supported_and_matches,
            )
            if anatomy_result.abstained:
                abstention_reasons.append("anatomy_model_abstained")
            elif not anatomy_supported_and_matches:
                abstention_reasons.append("selected_region_anatomy_mismatch")
        except Exception:
            abstention_reasons.append("anatomy_inference_failed")
    elif quality.accepted:
        limitations.append(
            "Anatomy support is unavailable because no validated anatomy adapter is loaded."
        )

    segmentation_adapter = runtime.adapters.get(ModelHead.SEGMENTATION)
    if (
        quality.accepted
        and anatomy_supported_and_matches
        and segmentation_adapter is not None
    ):
        invoked_heads.add(ModelHead.SEGMENTATION)
        try:
            raw_segmentation = segmentation_adapter.predict(image.rgb)
            if not isinstance(raw_segmentation, SegmentationPrediction):
                raise ModelAdapterError(
                    "The segmentation adapter returned the wrong output type."
                )
            # Validate and convert the model mask before marking this request complete.
            candidate_from_model_mask(image, raw_segmentation)
            segmentation_prediction = raw_segmentation
            segmentation_confidence = raw_segmentation.confidence
            successful_model_output = True
        except Exception:
            abstention_reasons.append("segmentation_inference_failed")
    elif quality.accepted and anatomy_supported_and_matches:
        limitations.append(
            "Candidate masks are unavailable because no validated segmentation adapter is loaded."
        )

    primary_complete = (
        quality.accepted
        and anatomy_supported_and_matches
        and segmentation_prediction is not None
    )
    candidate_mask: CandidateMask | None = None
    descriptors: VisualDescriptors | None = None
    if primary_complete and segmentation_prediction is not None:
        candidate_mask, descriptors, _ = candidate_from_model_mask(
            image,
            segmentation_prediction,
        )
        if candidate_mask is None:
            limitations.append(
                "The released segmentation model returned no thresholded candidate region."
            )

    appearance_output: ModelOutput | None = None
    if ModelHead.APPEARANCE in requested:
        appearance_adapter = runtime.adapters.get(ModelHead.APPEARANCE)
        if appearance_adapter is None:
            appearance_output = _gated_output("appearance")
        elif not primary_complete:
            appearance_output = _abstained_model_output(
                "appearance",
                "was not run because the primary analysis did not complete.",
            )
        else:
            invoked_heads.add(ModelHead.APPEARANCE)
            try:
                appearance_output = _classification_model_output(
                    appearance_adapter,
                    image,
                    head_name="appearance",
                    expected_labels=tuple(item.value for item in AppearanceClass),
                )
                successful_model_output = True
            except Exception:
                appearance_output = _abstained_model_output(
                    "appearance",
                    "failed for this image and exposed no prediction.",
                )
                abstention_reasons.append("appearance_inference_failed")

    disease_output: ModelOutput | None = None
    if ModelHead.DISEASE_RESEARCH in requested:
        disease_adapter = runtime.adapters.get(ModelHead.DISEASE_RESEARCH)
        if disease_adapter is None:
            disease_output = _gated_output("disease-category")
        elif not primary_complete:
            disease_output = _abstained_model_output(
                "disease-category",
                "was not run because the primary analysis did not complete.",
            )
        else:
            invoked_heads.add(ModelHead.DISEASE_RESEARCH)
            try:
                disease_output = _classification_model_output(
                    disease_adapter,
                    image,
                    head_name="disease-category",
                    expected_labels=tuple(item.value for item in DiseaseResearchClass),
                )
                successful_model_output = True
            except Exception:
                disease_output = _abstained_model_output(
                    "disease-category",
                    "failed for this image and exposed no prediction.",
                )
                abstention_reasons.append("disease_research_inference_failed")

    if primary_complete:
        status = AnalysisStatus.COMPLETE
    elif (
        quality.accepted
        and anatomy_prediction.confidence > 0
        and (
            not anatomy_prediction.supported
            or not anatomy_prediction.selected_region_matches
        )
    ):
        status = AnalysisStatus.UNSUPPORTED
    else:
        status = AnalysisStatus.ABSTAINED

    overall_confidence = (
        min(
            quality_confidence,
            anatomy_prediction.confidence,
            segmentation_confidence,
        )
        if primary_complete
        else 0.0
    )
    if not primary_complete:
        limitations.append("No completed image interpretation is available.")

    return AnalysisResult(
        capture_id=metadata.capture_id,
        region=metadata.selected_region,
        quality=quality,
        anatomy_prediction=anatomy_prediction,
        candidate_mask=candidate_mask,
        descriptors=descriptors,
        appearance_output=appearance_output,
        disease_research_output=disease_output,
        uncertainty=Uncertainty(
            overall_confidence=overall_confidence,
            image_quality_confidence=quality_confidence,
            dataset_similarity=None,
            model_agreement=None,
            limitations=limitations,
        ),
        abstention_reasons=list(dict.fromkeys(abstention_reasons)),
        model_versions=_invoked_model_versions(runtime, invoked_heads),
        input_origin=metadata.input_origin,
        analysis_origin=(
            AnalysisOrigin.LIVE_MODEL
            if successful_model_output
            else AnalysisOrigin.UNAVAILABLE
        ),
        status=status,
    )


def failed_analysis(metadata: AnalyzeMetadata) -> AnalysisResult:
    """Return a schema-valid unavailable result without substituting a fixture."""

    reason = "analysis_unavailable"
    return AnalysisResult(
        capture_id=metadata.capture_id,
        region=metadata.selected_region,
        quality=QualityResult(
            accepted=False,
            blur_score=0,
            exposure_score=0,
            glare_score=0,
            obstruction_score=0,
            face_detected=False,
            reasons=[reason],
        ),
        anatomy_prediction=AnatomyPrediction(
            region=None,
            confidence=0,
            supported=False,
            selected_region_matches=False,
        ),
        candidate_mask=None,
        descriptors=None,
        appearance_output=None,
        disease_research_output=None,
        uncertainty=Uncertainty(
            overall_confidence=0,
            image_quality_confidence=0,
            dataset_similarity=None,
            model_agreement=None,
            limitations=[
                "Analysis failed; no result or fixture substitution is available."
            ],
        ),
        abstention_reasons=[reason],
        model_versions=MODEL_VERSIONS,
        input_origin=metadata.input_origin,
        analysis_origin=AnalysisOrigin.UNAVAILABLE,
        status=AnalysisStatus.FAILED,
    )


def _orb_registration(
    baseline: SanitizedImage, current: SanitizedImage
) -> tuple[float, float, float, list[str], np.ndarray | None]:
    baseline_gray = cv2.cvtColor(baseline.bgr, cv2.COLOR_BGR2GRAY)
    current_gray = cv2.cvtColor(current.bgr, cv2.COLOR_BGR2GRAY)
    orb = cv2.ORB_create(nfeatures=1_200, fastThreshold=10)
    baseline_keypoints, baseline_descriptors = orb.detectAndCompute(baseline_gray, None)
    current_keypoints, current_descriptors = orb.detectAndCompute(current_gray, None)
    if (
        baseline_descriptors is None
        or current_descriptors is None
        or len(baseline_keypoints) < 8
        or len(current_keypoints) < 8
    ):
        return 0.0, 1.0, 0.0, ["insufficient_registration_features"], None

    matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    matches = sorted(
        matcher.match(baseline_descriptors, current_descriptors),
        key=lambda m: m.distance,
    )
    good = [match for match in matches if match.distance <= 64]
    if len(good) < 8:
        return 0.0, 1.0, 0.0, ["insufficient_feature_matches"], None

    source_points = np.float32(
        [baseline_keypoints[match.queryIdx].pt for match in good]
    ).reshape(-1, 1, 2)
    destination_points = np.float32(
        [current_keypoints[match.trainIdx].pt for match in good]
    ).reshape(-1, 1, 2)
    homography, inlier_mask = cv2.findHomography(
        source_points, destination_points, cv2.RANSAC, 3.0
    )
    if (
        homography is None
        or inlier_mask is None
        or homography.shape != (3, 3)
        or not np.all(np.isfinite(homography))
        or abs(float(np.linalg.det(homography))) < 1e-10
    ):
        return 0.0, 1.0, 0.0, ["registration_failed"], None

    inliers = inlier_mask.ravel().astype(bool)
    inlier_ratio = _clamp(float(np.mean(inliers)))
    projected = cv2.perspectiveTransform(source_points, homography)
    errors = np.linalg.norm(projected[:, 0, :] - destination_points[:, 0, :], axis=1)
    inlier_errors = errors[inliers]
    diagonal = max(math.hypot(*current_gray.shape[::-1]), 1.0)
    reprojection_error_ratio = (
        float(np.median(inlier_errors) / diagonal) if inlier_errors.size else 1.0
    )
    error_confidence = _clamp(1.0 - reprojection_error_ratio / 0.03)
    registration_confidence = _clamp(0.65 * inlier_ratio + 0.35 * error_confidence)
    reasons: list[str] = []
    if inlier_ratio < 0.60:
        reasons.append("registration_inlier_ratio_below_gate")
    if reprojection_error_ratio > 0.03:
        reasons.append("registration_reprojection_error_above_gate")
    return (
        inlier_ratio,
        reprojection_error_ratio,
        registration_confidence,
        reasons,
        homography,
    )


def compare_sanitized_images(
    baseline: SanitizedImage,
    current: SanitizedImage,
    metadata: CompareMetadata,
    runtime: ReleaseRuntimeState | None = None,
) -> ComparisonResult:
    runtime = RELEASE_RUNTIME if runtime is None else runtime
    baseline_quality, _ = assess_quality(baseline)
    current_quality, _ = assess_quality(current)
    segmentation_adapter = runtime.adapters.get(ModelHead.SEGMENTATION)
    reidentification_adapter = runtime.adapters.get(ModelHead.LESION_REIDENTIFICATION)
    baseline_candidate: CandidateMask | None = None
    baseline_descriptors: VisualDescriptors | None = None
    baseline_component: np.ndarray | None = None
    current_candidate: CandidateMask | None = None
    current_descriptors: VisualDescriptors | None = None
    current_component: np.ndarray | None = None
    candidate_match_score: float | None = None
    learned_output_available = False
    invoked_heads: set[ModelHead] = set()
    suppression_reasons: list[str] = []

    if (
        segmentation_adapter is not None
        and baseline_quality.accepted
        and current_quality.accepted
    ):
        invoked_heads.add(ModelHead.SEGMENTATION)
        try:
            baseline_segmentation = segmentation_adapter.predict(baseline.rgb)
            current_segmentation = segmentation_adapter.predict(current.rgb)
            if not isinstance(
                baseline_segmentation, SegmentationPrediction
            ) or not isinstance(
                current_segmentation,
                SegmentationPrediction,
            ):
                raise ModelAdapterError(
                    "The segmentation adapter returned the wrong output type."
                )
            (
                baseline_candidate,
                baseline_descriptors,
                baseline_component,
            ) = candidate_from_model_mask(baseline, baseline_segmentation)
            (
                current_candidate,
                current_descriptors,
                current_component,
            ) = candidate_from_model_mask(current, current_segmentation)
            learned_output_available = True
        except Exception:
            baseline_candidate = None
            baseline_descriptors = None
            current_candidate = None
            current_descriptors = None
            suppression_reasons.append("segmentation_inference_failed")

    if (
        reidentification_adapter is not None
        and baseline_quality.accepted
        and current_quality.accepted
    ):
        invoked_heads.add(ModelHead.LESION_REIDENTIFICATION)
        try:
            baseline_embedding = reidentification_adapter.predict(baseline.rgb)
            current_embedding = reidentification_adapter.predict(current.rgb)
            if not isinstance(
                baseline_embedding, EmbeddingPrediction
            ) or not isinstance(
                current_embedding,
                EmbeddingPrediction,
            ):
                raise ModelAdapterError(
                    "The re-identification adapter returned the wrong output type."
                )
            baseline_values = np.asarray(baseline_embedding.values, dtype=np.float64)
            current_values = np.asarray(current_embedding.values, dtype=np.float64)
            if (
                baseline_values.ndim != 1
                or current_values.ndim != 1
                or baseline_values.shape != current_values.shape
                or baseline_values.size < 2
                or not np.all(np.isfinite(baseline_values))
                or not np.all(np.isfinite(current_values))
            ):
                raise ModelAdapterError("Re-identification embeddings are invalid.")
            baseline_norm = float(np.linalg.norm(baseline_values))
            current_norm = float(np.linalg.norm(current_values))
            if baseline_norm <= 1e-12 or current_norm <= 1e-12:
                raise ModelAdapterError("Re-identification embeddings have zero norm.")
            cosine_similarity = float(
                np.dot(baseline_values, current_values) / (baseline_norm * current_norm)
            )
            candidate_match_score = _clamp((cosine_similarity + 1.0) / 2.0)
            learned_output_available = True
        except Exception:
            candidate_match_score = None
            suppression_reasons.append("lesion_reidentification_inference_failed")

    (
        inlier_ratio,
        reprojection_error_ratio,
        registration_confidence,
        registration_reasons,
        homography,
    ) = _orb_registration(baseline, current)
    suppression_reasons.extend(registration_reasons)

    if not baseline_quality.accepted:
        suppression_reasons.append("baseline_image_quality_rejected")
    if not current_quality.accepted:
        suppression_reasons.append("current_image_quality_rejected")
    if not metadata.user_confirmed_match:
        suppression_reasons.append("user_confirmation_required")

    # Re-identification is an optional automated suggestion. Once the user has
    # explicitly reviewed and confirmed the pair, a missing suggestion must not
    # block an otherwise valid geometric comparison.
    if not metadata.user_confirmed_match:
        if reidentification_adapter is None:
            suppression_reasons.append("lesion_reidentification_release_gate_unmet")
        elif candidate_match_score is None:
            suppression_reasons.append("candidate_match_score_unavailable")
    if segmentation_adapter is None:
        suppression_reasons.append("segmentation_release_gate_unmet")
    else:
        if baseline_candidate is None or baseline_descriptors is None:
            suppression_reasons.append("baseline_candidate_region_unavailable")
        if current_candidate is None or current_descriptors is None:
            suppression_reasons.append("current_candidate_region_unavailable")

    repeated_capture_gate_passed = runtime.repeated_capture_area_error is not None
    if not repeated_capture_gate_passed:
        suppression_reasons.append("repeated_capture_area_error_gate_unmet")

    # Prior-analysis metadata binds capture and region identity, but it is
    # supplied by the caller and therefore never drives a live measurement.
    # Candidate areas are recomputed from the two sanitized images by the
    # currently deployed segmentation head.
    baseline_area: float | None = None
    if baseline_component is not None and homography is not None:
        current_height, current_width = current.bgr.shape[:2]
        registered_baseline = cv2.warpPerspective(
            baseline_component,
            homography,
            (current_width, current_height),
            flags=cv2.INTER_NEAREST,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=0,
        )
        baseline_area = _clamp(
            float(np.count_nonzero(registered_baseline))
            / max(float(current_width * current_height), 1.0)
        )
    current_area = (
        _clamp(
            float(np.count_nonzero(current_component))
            / max(float(current_component.size), 1.0)
        )
        if current_component is not None
        else None
    )
    if baseline_area is None:
        suppression_reasons.append("registered_baseline_candidate_area_unavailable")
    if current_area is None:
        suppression_reasons.append("current_candidate_area_unavailable")

    comparable = not suppression_reasons
    normalized_change: float | None = None
    if comparable and baseline_area is not None and current_area is not None:
        if baseline_area > 0:
            normalized_change = (current_area - baseline_area) / baseline_area
        else:
            comparable = False
            suppression_reasons.append("baseline_candidate_area_zero")

    return ComparisonResult(
        baseline_capture_id=metadata.baseline_capture_id,
        current_capture_id=metadata.current_capture_id,
        region=metadata.region,
        candidate_match_score=candidate_match_score,
        user_confirmed_match=metadata.user_confirmed_match,
        registration_confidence=registration_confidence,
        inlier_ratio=inlier_ratio,
        reprojection_error_ratio=reprojection_error_ratio,
        normalized_change=normalized_change,
        comparable=comparable,
        suppression_reasons=list(dict.fromkeys(suppression_reasons)),
        model_versions=_invoked_model_versions(runtime, invoked_heads),
        input_origin=metadata.input_origin,
        analysis_origin=(
            AnalysisOrigin.LIVE_MODEL
            if learned_output_available
            else AnalysisOrigin.UNAVAILABLE
        ),
    )


def failed_comparison(metadata: CompareMetadata) -> ComparisonResult:
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
        comparable=False,
        suppression_reasons=["analysis_unavailable"],
        model_versions=MODEL_VERSIONS,
        input_origin=metadata.input_origin,
        analysis_origin=AnalysisOrigin.UNAVAILABLE,
    )

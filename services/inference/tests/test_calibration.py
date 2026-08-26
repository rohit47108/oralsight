from __future__ import annotations

import cv2
import numpy as np
import pytest

from oralsight_api.calibration import (
    CALIBRATION_DICTIONARY,
    CALIBRATION_MARKER_ID,
    EXPECTED_NEUTRAL_PATCH_VALUES,
    estimate_calibrated_bounding_box,
    estimate_neutral_color_reference,
)
from oralsight_api.model_adapters import SegmentationPrediction
from oralsight_api.processing import SanitizedImage, candidate_from_model_mask


def _calibration_scene(*, marker_id: int = CALIBRATION_MARKER_ID) -> np.ndarray:
    image = np.full((600, 800, 3), 255, dtype=np.uint8)
    dictionary = cv2.aruco.getPredefinedDictionary(CALIBRATION_DICTIONARY)
    marker = cv2.aruco.generateImageMarker(dictionary, marker_id, 200)
    image[180:380, 60:260] = cv2.cvtColor(marker, cv2.COLOR_GRAY2BGR)
    return image


def _neutral_reference_scene(
    *,
    marker_id: int = CALIBRATION_MARKER_ID,
    occluded_patch: int | None = None,
    rgb_scale: tuple[float, float, float] = (1.0, 1.0, 1.0),
    rgb_offset: tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> tuple[np.ndarray, tuple[float, float, float, float]]:
    """Render the versioned marker/patch geometry and a nearby target."""

    image_rgb = np.full((600, 800, 3), 245, dtype=np.uint8)
    dictionary = cv2.aruco.getPredefinedDictionary(CALIBRATION_DICTIONARY)
    marker = cv2.aruco.generateImageMarker(dictionary, marker_id, 120)
    image_rgb[180:300, 60:180] = cv2.cvtColor(marker, cv2.COLOR_GRAY2RGB)

    # The generated card places 9 mm patches 38 mm to the right and 6 mm
    # below the 20 mm marker's top-left corner, with an 11 mm pitch.
    for index, value in enumerate(EXPECTED_NEUTRAL_PATCH_VALUES):
        left = 60 + round((38 + index * 11) / 20 * 120)
        top = 180 + round(6 / 20 * 120)
        side = round(9 / 20 * 120)
        image_rgb[top : top + side, left : left + side] = value
    if occluded_patch is not None:
        left = 60 + round((38 + occluded_patch * 11) / 20 * 120)
        top = 180 + round(6 / 20 * 120)
        side = round(9 / 20 * 120)
        image_rgb[top : top + side, left : left + side] = (220, 30, 190)

    target_left, target_top, target_width, target_height = 300, 360, 120, 80
    image_rgb[
        target_top : target_top + target_height,
        target_left : target_left + target_width,
    ] = (180, 80, 70)
    transformed = np.clip(
        image_rgb.astype(np.float32) * np.asarray(rgb_scale, dtype=np.float32)
        + np.asarray(rgb_offset, dtype=np.float32),
        0,
        255,
    ).astype(np.uint8)
    normalized_target = (
        target_left / image_rgb.shape[1],
        target_top / image_rgb.shape[0],
        target_width / image_rgb.shape[1],
        target_height / image_rgb.shape[0],
    )
    return cv2.cvtColor(transformed, cv2.COLOR_RGB2BGR), normalized_target


def _candidate_prediction(
    image_bgr: np.ndarray,
    bounding_box: tuple[float, float, float, float],
) -> SegmentationPrediction:
    height, width = image_bgr.shape[:2]
    x, y, box_width, box_height = bounding_box
    probabilities = np.zeros((height, width), dtype=np.float32)
    left = round(x * width)
    top = round(y * height)
    right = round((x + box_width) * width)
    bottom = round((y + box_height) * height)
    probabilities[top:bottom, left:right] = 1.0
    return SegmentationPrediction(
        probabilities=probabilities,
        threshold=0.5,
        confidence=0.95,
    )


def _sanitized(image_bgr: np.ndarray) -> SanitizedImage:
    return SanitizedImage(
        jpeg_bytes=b"test-only",
        rgb=cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB),
        bgr=image_bgr,
    )


def test_calibration_estimates_nearby_normalized_box() -> None:
    result = estimate_calibrated_bounding_box(
        _calibration_scene(),
        (360 / 800, 230 / 600, 100 / 800, 50 / 600),
        plane_confirmed=True,
    )

    assert result.valid is True
    assert result.suppression_reasons == ()
    assert result.estimated_width_mm == pytest.approx(10.0, abs=0.2)
    assert result.estimated_height_mm == pytest.approx(5.0, abs=0.2)
    assert result.estimated_area_mm2 == pytest.approx(50.0, abs=3.0)


def test_calibration_suppresses_without_plane_confirmation() -> None:
    result = estimate_calibrated_bounding_box(
        _calibration_scene(),
        (360 / 800, 230 / 600, 100 / 800, 50 / 600),
        plane_confirmed=False,
    )

    assert result.valid is False
    assert result.estimated_width_mm is None
    assert "target_plane_not_confirmed" in result.suppression_reasons


def test_calibration_suppresses_wrong_or_missing_marker() -> None:
    wrong = estimate_calibrated_bounding_box(
        _calibration_scene(marker_id=3),
        (360 / 800, 230 / 600, 100 / 800, 50 / 600),
        plane_confirmed=True,
    )
    missing = estimate_calibrated_bounding_box(
        np.full((600, 800, 3), 255, dtype=np.uint8),
        (360 / 800, 230 / 600, 100 / 800, 50 / 600),
        plane_confirmed=True,
    )

    assert wrong.valid is False
    assert wrong.suppression_reasons == ("calibration_marker_mismatch",)
    assert missing.valid is False
    assert missing.suppression_reasons == ("calibration_marker_not_found",)


def test_calibration_suppresses_invalid_or_distant_target() -> None:
    invalid = estimate_calibrated_bounding_box(
        _calibration_scene(),
        (0.9, 0.2, 0.2, 0.1),
        plane_confirmed=True,
    )
    distant = estimate_calibrated_bounding_box(
        _calibration_scene(),
        (0.88, 0.85, 0.08, 0.08),
        plane_confirmed=True,
    )

    assert invalid.valid is False
    assert invalid.suppression_reasons == ("invalid_candidate_bounds",)
    assert distant.valid is False
    assert "calibration_marker_too_far_from_target" in distant.suppression_reasons


def test_neutral_reference_corrects_only_color_descriptors_for_valid_card() -> None:
    baseline_bgr, target = _neutral_reference_scene()
    cast_bgr, _ = _neutral_reference_scene(
        rgb_scale=(0.96, 0.82, 0.68),
        rgb_offset=(8.0, 12.0, 18.0),
    )
    reference = estimate_neutral_color_reference(
        cast_bgr,
        target,
        plane_confirmed=True,
    )

    assert reference.applied is True
    assert reference.suppression_reasons == ()
    assert reference.method == "neutral-grayscale-patches-affine-rgb-v1"

    prediction = _candidate_prediction(cast_bgr, target)
    baseline_candidate, baseline_descriptors, baseline_component = (
        candidate_from_model_mask(
            _sanitized(baseline_bgr),
            _candidate_prediction(baseline_bgr, target),
        )
    )
    corrected_candidate, corrected_descriptors, corrected_component = (
        candidate_from_model_mask(
            _sanitized(cast_bgr),
            prediction,
            color_reference=reference,
        )
    )
    _, uncorrected_descriptors, _ = candidate_from_model_mask(
        _sanitized(cast_bgr), prediction
    )

    assert baseline_candidate == corrected_candidate
    assert np.array_equal(baseline_component, corrected_component)
    assert baseline_descriptors is not None
    assert corrected_descriptors is not None
    assert uncorrected_descriptors is not None
    assert corrected_descriptors.mean_redness == pytest.approx(
        baseline_descriptors.mean_redness,
        abs=0.015,
    )
    assert corrected_descriptors.mean_brightness == pytest.approx(
        baseline_descriptors.mean_brightness,
        abs=0.015,
    )
    assert corrected_descriptors.texture_contrast == pytest.approx(
        uncorrected_descriptors.texture_contrast
    )


def test_neutral_reference_abstains_for_missing_or_occluded_patches() -> None:
    complete_bgr, target = _neutral_reference_scene()
    missing_bgr = complete_bgr[:, :475].copy()
    missing_target = (
        target[0] * complete_bgr.shape[1] / missing_bgr.shape[1],
        target[1],
        target[2] * complete_bgr.shape[1] / missing_bgr.shape[1],
        target[3],
    )
    occluded_bgr, _ = _neutral_reference_scene(occluded_patch=2)

    missing = estimate_neutral_color_reference(
        missing_bgr,
        missing_target,
        plane_confirmed=True,
    )
    occluded = estimate_neutral_color_reference(
        occluded_bgr,
        target,
        plane_confirmed=True,
    )

    assert missing.applied is False
    assert missing.suppression_reasons == ("color_reference_patch_out_of_frame",)
    assert occluded.applied is False
    assert occluded.suppression_reasons in {
        ("color_reference_patch_order_invalid",),
        ("color_reference_patch_not_neutral",),
    }


def test_neutral_reference_abstains_for_partial_patch_occlusion() -> None:
    image_bgr, target = _neutral_reference_scene()
    # A partial colored obstruction keeps the center median plausible but makes
    # the patch nonuniform; the fit must still abstain.
    image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    patch_left = 60 + round((38 + 1 * 11) / 20 * 120)
    patch_top = 180 + round(6 / 20 * 120)
    patch_side = round(9 / 20 * 120)
    image_rgb[
        patch_top : patch_top + patch_side,
        patch_left : patch_left + patch_side // 3,
    ] = (210, 25, 170)

    result = estimate_neutral_color_reference(
        cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR),
        target,
        plane_confirmed=True,
    )

    assert result.applied is False
    assert result.suppression_reasons == ("color_reference_patch_nonuniform",)


def test_neutral_reference_rejects_wrong_card_without_affecting_size_gate() -> None:
    wrong_bgr, target = _neutral_reference_scene(marker_id=3)
    no_patches = _calibration_scene()
    no_patch_target = (360 / 800, 230 / 600, 100 / 800, 50 / 600)

    wrong = estimate_neutral_color_reference(
        wrong_bgr,
        target,
        plane_confirmed=True,
    )
    size = estimate_calibrated_bounding_box(
        no_patches,
        no_patch_target,
        plane_confirmed=True,
    )
    color = estimate_neutral_color_reference(
        no_patches,
        no_patch_target,
        plane_confirmed=True,
    )

    assert wrong.applied is False
    assert wrong.suppression_reasons == ("calibration_marker_mismatch",)
    assert size.valid is True
    assert color.applied is False
    assert color.suppression_reasons == ("color_reference_patch_out_of_frame",)

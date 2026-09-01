"""Physical reference-card detection for optional approximate measurements.

The calibration card must stay outside the mouth and must not touch tissue. A
measurement is returned only when the expected marker is clear, the candidate
is near the marker, and the capture workflow explicitly confirms that both are
approximately on the same plane. This module does not turn a phone image into a
clinical measuring instrument.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from math import hypot
from typing import Final

import cv2
import numpy as np

CALIBRATION_CARD_VERSION: Final[str] = "stoma3d-calibration-v1"
CALIBRATION_DICTIONARY: Final[int] = cv2.aruco.DICT_4X4_50
CALIBRATION_MARKER_ID: Final[int] = 17
CALIBRATION_MARKER_SIDE_MM: Final[float] = 20.0
MIN_MARKER_EDGE_PX: Final[float] = 40.0
MAX_EDGE_VARIATION: Final[float] = 0.22
MAX_TARGET_DISTANCE_MARKER_SIDES: Final[float] = 3.0
EXPECTED_NEUTRAL_PATCH_VALUES: Final[tuple[int, int, int, int]] = (35, 100, 170, 235)
NEUTRAL_COLOR_REFERENCE_VERSION: Final[str] = "neutral-grayscale-patches-affine-rgb-v1"
# Coordinates are millimeters from the detected marker's top-left corner and
# match scripts/generate_calibration_cards.py. Only the interior is sampled so
# the printed border cannot influence the fit.
_PATCH_LEFT_MM: Final[tuple[float, float, float, float]] = (38.0, 49.0, 60.0, 71.0)
_PATCH_TOP_MM: Final[float] = 6.0
_PATCH_SIDE_MM: Final[float] = 9.0
_PATCH_INSET_MM: Final[float] = 1.6
_MIN_PATCH_PIXELS: Final[int] = 64
_MAX_PATCH_CHANNEL_MAD: Final[float] = 8.0
_MAX_PATCH_CHANNEL_SPREAD: Final[float] = 26.0
_MIN_PATCH_STEP: Final[float] = 12.0
_MIN_CHANNEL_RANGE: Final[float] = 105.0
_MIN_COLOR_SCALE: Final[float] = 0.65
_MAX_COLOR_SCALE: Final[float] = 1.55
_MAX_COLOR_OFFSET: Final[float] = 40.0
_MAX_PATCH_FIT_ERROR: Final[float] = 12.0


@dataclass(frozen=True)
class CalibrationEstimate:
    card_version: str
    marker_id: int | None
    marker_side_mm: float
    valid: bool
    plane_confirmed: bool
    scale_uncertainty: float | None
    estimated_width_mm: float | None
    estimated_height_mm: float | None
    estimated_area_mm2: float | None
    confidence: float
    suppression_reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class NeutralColorReference:
    """Optional, fail-closed transform for two color descriptor fields only."""

    card_version: str
    marker_id: int | None
    applied: bool
    method: str
    rgb_scales: tuple[float, float, float] | None
    rgb_offsets: tuple[float, float, float] | None
    confidence: float
    suppression_reasons: tuple[str, ...]

    def correct_rgb(self, pixels_rgb: np.ndarray) -> np.ndarray:
        """Return corrected float RGB values without mutating source pixels."""

        copied = np.asarray(pixels_rgb, dtype=np.float32).copy()
        if (
            not self.applied
            or self.rgb_scales is None
            or self.rgb_offsets is None
            or copied.shape[-1:] != (3,)
        ):
            return copied
        scales = np.asarray(self.rgb_scales, dtype=np.float32)
        offsets = np.asarray(self.rgb_offsets, dtype=np.float32)
        return np.clip(copied * scales + offsets, 0.0, 255.0)


def _color_suppressed(
    *reasons: str,
    marker_id: int | None = None,
    confidence: float = 0.0,
) -> NeutralColorReference:
    return NeutralColorReference(
        card_version=CALIBRATION_CARD_VERSION,
        marker_id=marker_id,
        applied=False,
        method=NEUTRAL_COLOR_REFERENCE_VERSION,
        rgb_scales=None,
        rgb_offsets=None,
        confidence=max(0.0, min(1.0, confidence)),
        suppression_reasons=tuple(dict.fromkeys(reasons)),
    )


def _suppressed(
    *reasons: str,
    marker_id: int | None = None,
    plane_confirmed: bool = False,
    scale_uncertainty: float | None = None,
    confidence: float = 0.0,
    marker_side_mm: float = CALIBRATION_MARKER_SIDE_MM,
) -> CalibrationEstimate:
    return CalibrationEstimate(
        card_version=CALIBRATION_CARD_VERSION,
        marker_id=marker_id,
        marker_side_mm=marker_side_mm,
        valid=False,
        plane_confirmed=plane_confirmed,
        scale_uncertainty=scale_uncertainty,
        estimated_width_mm=None,
        estimated_height_mm=None,
        estimated_area_mm2=None,
        confidence=max(0.0, min(1.0, confidence)),
        suppression_reasons=tuple(dict.fromkeys(reasons)),
    )


def _edge_lengths(corners: np.ndarray) -> np.ndarray:
    rolled = np.roll(corners, -1, axis=0)
    return np.linalg.norm(rolled - corners, axis=1)


def _normalized_box_points(
    bounding_box: tuple[float, float, float, float],
    *,
    image_width: int,
    image_height: int,
) -> np.ndarray:
    x, y, width, height = bounding_box
    values = (x, y, width, height)
    if not all(np.isfinite(value) for value in values):
        raise ValueError("Candidate bounding box must contain finite values.")
    if width <= 0 or height <= 0 or x < 0 or y < 0 or x + width > 1 or y + height > 1:
        raise ValueError(
            "Candidate bounding box must stay within normalized image bounds."
        )
    left = x * image_width
    top = y * image_height
    right = (x + width) * image_width
    bottom = (y + height) * image_height
    return np.asarray(
        [[left, top], [right, top], [right, bottom], [left, bottom]],
        dtype=np.float32,
    )


def estimate_calibrated_bounding_box(
    image_bgr: np.ndarray,
    bounding_box: tuple[float, float, float, float],
    *,
    plane_confirmed: bool,
    expected_marker_id: int = CALIBRATION_MARKER_ID,
    marker_side_mm: float = CALIBRATION_MARKER_SIDE_MM,
) -> CalibrationEstimate:
    """Estimate candidate dimensions from a nearby, known-size ArUco marker.

    The bounding box uses normalized ``x, y, width, height`` coordinates. Null
    dimensions are returned whenever a release condition is missing.
    """

    if (
        not isinstance(image_bgr, np.ndarray)
        or image_bgr.ndim not in {2, 3}
        or image_bgr.shape[0] < 64
        or image_bgr.shape[1] < 64
    ):
        return _suppressed("invalid_image", plane_confirmed=plane_confirmed)
    if not np.isfinite(marker_side_mm) or marker_side_mm <= 0:
        return _suppressed("invalid_marker_dimensions", plane_confirmed=plane_confirmed)

    try:
        target_points = _normalized_box_points(
            bounding_box,
            image_width=int(image_bgr.shape[1]),
            image_height=int(image_bgr.shape[0]),
        )
    except ValueError:
        return _suppressed(
            "invalid_candidate_bounds",
            plane_confirmed=plane_confirmed,
            marker_side_mm=marker_side_mm,
        )

    if image_bgr.ndim == 3:
        if image_bgr.shape[2] != 3:
            return _suppressed(
                "invalid_image",
                plane_confirmed=plane_confirmed,
                marker_side_mm=marker_side_mm,
            )
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    else:
        gray = image_bgr

    dictionary = cv2.aruco.getPredefinedDictionary(CALIBRATION_DICTIONARY)
    parameters = cv2.aruco.DetectorParameters()
    detector = cv2.aruco.ArucoDetector(dictionary, parameters)
    detected_corners, detected_ids, _ = detector.detectMarkers(gray)
    if detected_ids is None:
        return _suppressed(
            "calibration_marker_not_found",
            plane_confirmed=plane_confirmed,
            marker_side_mm=marker_side_mm,
        )

    flat_ids = detected_ids.reshape(-1).tolist()
    matching_indices = [
        index for index, value in enumerate(flat_ids) if value == expected_marker_id
    ]
    if not matching_indices:
        return _suppressed(
            "calibration_marker_mismatch",
            marker_id=int(flat_ids[0]) if flat_ids else None,
            plane_confirmed=plane_confirmed,
            marker_side_mm=marker_side_mm,
        )
    marker_id = expected_marker_id
    marker_corners = np.asarray(
        detected_corners[matching_indices[0]], dtype=np.float32
    ).reshape(4, 2)
    edge_lengths = _edge_lengths(marker_corners)
    mean_edge = float(edge_lengths.mean())
    if mean_edge <= 0:
        return _suppressed(
            "calibration_marker_invalid",
            marker_id=marker_id,
            plane_confirmed=plane_confirmed,
            marker_side_mm=marker_side_mm,
        )
    edge_variation = float(edge_lengths.std() / mean_edge)
    reasons: list[str] = []
    if float(edge_lengths.min()) < MIN_MARKER_EDGE_PX:
        reasons.append("calibration_marker_too_small")
    if edge_variation > MAX_EDGE_VARIATION:
        reasons.append("calibration_marker_pose_unreliable")
    if not plane_confirmed:
        reasons.append("target_plane_not_confirmed")

    marker_center = marker_corners.mean(axis=0)
    target_center = target_points.mean(axis=0)
    center_distance = hypot(
        float(target_center[0] - marker_center[0]),
        float(target_center[1] - marker_center[1]),
    )
    distance_in_marker_sides = center_distance / mean_edge
    if distance_in_marker_sides > MAX_TARGET_DISTANCE_MARKER_SIDES:
        reasons.append("calibration_marker_too_far_from_target")

    size_confidence = min(1.0, mean_edge / 160.0)
    pose_confidence = max(0.0, 1.0 - edge_variation / MAX_EDGE_VARIATION)
    distance_confidence = max(
        0.0, 1.0 - distance_in_marker_sides / MAX_TARGET_DISTANCE_MARKER_SIDES
    )
    confidence = min(size_confidence, pose_confidence, distance_confidence)
    if reasons:
        return _suppressed(
            *reasons,
            marker_id=marker_id,
            plane_confirmed=plane_confirmed,
            scale_uncertainty=edge_variation,
            confidence=confidence,
            marker_side_mm=marker_side_mm,
        )

    canonical_marker = np.asarray(
        [
            [0.0, 0.0],
            [marker_side_mm, 0.0],
            [marker_side_mm, marker_side_mm],
            [0.0, marker_side_mm],
        ],
        dtype=np.float32,
    )
    homography = cv2.getPerspectiveTransform(marker_corners, canonical_marker)
    projected = cv2.perspectiveTransform(target_points.reshape(1, 4, 2), homography)[0]
    top_width = float(np.linalg.norm(projected[1] - projected[0]))
    bottom_width = float(np.linalg.norm(projected[2] - projected[3]))
    left_height = float(np.linalg.norm(projected[3] - projected[0]))
    right_height = float(np.linalg.norm(projected[2] - projected[1]))
    estimated_width = (top_width + bottom_width) / 2.0
    estimated_height = (left_height + right_height) / 2.0
    if (
        not np.isfinite(estimated_width)
        or not np.isfinite(estimated_height)
        or estimated_width <= 0
        or estimated_height <= 0
    ):
        return _suppressed(
            "calibration_projection_failed",
            marker_id=marker_id,
            plane_confirmed=True,
            scale_uncertainty=edge_variation,
            confidence=confidence,
            marker_side_mm=marker_side_mm,
        )

    return CalibrationEstimate(
        card_version=CALIBRATION_CARD_VERSION,
        marker_id=marker_id,
        marker_side_mm=marker_side_mm,
        valid=True,
        plane_confirmed=True,
        scale_uncertainty=edge_variation,
        estimated_width_mm=estimated_width,
        estimated_height_mm=estimated_height,
        estimated_area_mm2=estimated_width * estimated_height,
        confidence=max(0.0, min(1.0, confidence)),
        suppression_reasons=(),
    )


def estimate_neutral_color_reference(
    image_bgr: np.ndarray,
    bounding_box: tuple[float, float, float, float],
    *,
    plane_confirmed: bool,
    expected_marker_id: int = CALIBRATION_MARKER_ID,
    marker_side_mm: float = CALIBRATION_MARKER_SIDE_MM,
) -> NeutralColorReference:
    """Fit a bounded RGB transform from all four versioned neutral patches.

    The physical-size gate is reused for marker identity, pose, same-plane
    confirmation, and target proximity. Failure to recover neutral patches has
    no effect on that independent size estimate. The returned transform is
    intended only for mean color descriptors and never changes image bytes.
    """

    scale_estimate = estimate_calibrated_bounding_box(
        image_bgr,
        bounding_box,
        plane_confirmed=plane_confirmed,
        expected_marker_id=expected_marker_id,
        marker_side_mm=marker_side_mm,
    )
    if not scale_estimate.valid:
        return _color_suppressed(
            *scale_estimate.suppression_reasons,
            marker_id=scale_estimate.marker_id,
            confidence=scale_estimate.confidence,
        )

    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    detector = cv2.aruco.ArucoDetector(
        cv2.aruco.getPredefinedDictionary(CALIBRATION_DICTIONARY),
        cv2.aruco.DetectorParameters(),
    )
    detected_corners, detected_ids, _ = detector.detectMarkers(gray)
    if detected_ids is None:
        return _color_suppressed("calibration_marker_not_found")
    flat_ids = detected_ids.reshape(-1).tolist()
    matching = [
        index
        for index, marker_id in enumerate(flat_ids)
        if marker_id == expected_marker_id
    ]
    if not matching:
        return _color_suppressed(
            "calibration_marker_mismatch",
            marker_id=int(flat_ids[0]) if flat_ids else None,
        )
    marker_corners = np.asarray(
        detected_corners[matching[0]], dtype=np.float32
    ).reshape(4, 2)
    canonical_marker = np.asarray(
        [
            [0.0, 0.0],
            [marker_side_mm, 0.0],
            [marker_side_mm, marker_side_mm],
            [0.0, marker_side_mm],
        ],
        dtype=np.float32,
    )
    marker_to_image = cv2.getPerspectiveTransform(canonical_marker, marker_corners)
    height, width = image_bgr.shape[:2]
    patch_medians: list[np.ndarray] = []
    uniformity_scores: list[float] = []

    for patch_left in _PATCH_LEFT_MM:
        patch_canonical = np.asarray(
            [
                [patch_left + _PATCH_INSET_MM, _PATCH_TOP_MM + _PATCH_INSET_MM],
                [
                    patch_left + _PATCH_SIDE_MM - _PATCH_INSET_MM,
                    _PATCH_TOP_MM + _PATCH_INSET_MM,
                ],
                [
                    patch_left + _PATCH_SIDE_MM - _PATCH_INSET_MM,
                    _PATCH_TOP_MM + _PATCH_SIDE_MM - _PATCH_INSET_MM,
                ],
                [
                    patch_left + _PATCH_INSET_MM,
                    _PATCH_TOP_MM + _PATCH_SIDE_MM - _PATCH_INSET_MM,
                ],
            ],
            dtype=np.float32,
        )
        projected = cv2.perspectiveTransform(
            patch_canonical.reshape(1, 4, 2), marker_to_image
        )[0]
        if (
            not np.all(np.isfinite(projected))
            or np.any(projected[:, 0] < 1)
            or np.any(projected[:, 0] > width - 2)
            or np.any(projected[:, 1] < 1)
            or np.any(projected[:, 1] > height - 2)
        ):
            return _color_suppressed(
                "color_reference_patch_out_of_frame",
                marker_id=expected_marker_id,
                confidence=scale_estimate.confidence,
            )

        patch_mask = np.zeros((height, width), dtype=np.uint8)
        cv2.fillConvexPoly(
            patch_mask,
            np.round(projected).astype(np.int32),
            255,
            lineType=cv2.LINE_8,
        )
        patch_bgr = image_bgr[patch_mask > 0]
        if patch_bgr.shape[0] < _MIN_PATCH_PIXELS:
            return _color_suppressed(
                "color_reference_patch_too_small",
                marker_id=expected_marker_id,
                confidence=scale_estimate.confidence,
            )
        patch_rgb = patch_bgr[:, ::-1].astype(np.float32)
        median = np.median(patch_rgb, axis=0)
        median_absolute_deviation = np.median(np.abs(patch_rgb - median), axis=0)
        robust_spread = np.percentile(patch_rgb, 95, axis=0) - np.percentile(
            patch_rgb, 5, axis=0
        )
        if (
            float(np.max(median_absolute_deviation)) > _MAX_PATCH_CHANNEL_MAD
            or float(np.max(robust_spread)) > _MAX_PATCH_CHANNEL_SPREAD
        ):
            return _color_suppressed(
                "color_reference_patch_nonuniform",
                marker_id=expected_marker_id,
                confidence=scale_estimate.confidence,
            )
        patch_medians.append(median)
        uniformity_scores.append(
            max(0.0, 1.0 - float(np.max(robust_spread)) / _MAX_PATCH_CHANNEL_SPREAD)
        )

    observed = np.asarray(patch_medians, dtype=np.float64)
    if observed.shape != (4, 3) or not np.all(np.isfinite(observed)):
        return _color_suppressed(
            "color_reference_patch_invalid",
            marker_id=expected_marker_id,
            confidence=scale_estimate.confidence,
        )
    channel_steps = np.diff(observed, axis=0)
    if np.any(channel_steps < _MIN_PATCH_STEP):
        return _color_suppressed(
            "color_reference_patch_order_invalid",
            marker_id=expected_marker_id,
            confidence=scale_estimate.confidence,
        )
    if np.any(observed[-1] - observed[0] < _MIN_CHANNEL_RANGE):
        return _color_suppressed(
            "color_reference_dynamic_range_too_low",
            marker_id=expected_marker_id,
            confidence=scale_estimate.confidence,
        )
    if np.any(observed[0] <= 5.0) or np.any(observed[-1] >= 250.0):
        return _color_suppressed(
            "color_reference_patch_clipped",
            marker_id=expected_marker_id,
            confidence=scale_estimate.confidence,
        )

    expected = np.asarray(EXPECTED_NEUTRAL_PATCH_VALUES, dtype=np.float64)
    scales: list[float] = []
    offsets: list[float] = []
    fitted = np.empty_like(observed)
    for channel in range(3):
        design = np.column_stack((observed[:, channel], np.ones(4)))
        coefficients, _, _, _ = np.linalg.lstsq(design, expected, rcond=None)
        channel_scale, channel_offset = (
            float(coefficients[0]),
            float(coefficients[1]),
        )
        if (
            not np.isfinite(channel_scale)
            or not np.isfinite(channel_offset)
            or not _MIN_COLOR_SCALE <= channel_scale <= _MAX_COLOR_SCALE
            or abs(channel_offset) > _MAX_COLOR_OFFSET
        ):
            return _color_suppressed(
                "color_reference_transform_unsafe",
                marker_id=expected_marker_id,
                confidence=scale_estimate.confidence,
            )
        scales.append(channel_scale)
        offsets.append(channel_offset)
        fitted[:, channel] = observed[:, channel] * channel_scale + channel_offset

    residual = np.abs(fitted - expected[:, None])
    if float(np.max(residual)) > _MAX_PATCH_FIT_ERROR:
        return _color_suppressed(
            "color_reference_patch_not_neutral",
            marker_id=expected_marker_id,
            confidence=scale_estimate.confidence,
        )
    fit_confidence = max(
        0.0,
        1.0 - float(np.sqrt(np.mean(np.square(residual)))) / _MAX_PATCH_FIT_ERROR,
    )
    confidence = min(
        scale_estimate.confidence,
        min(uniformity_scores, default=0.0),
        fit_confidence,
    )
    return NeutralColorReference(
        card_version=CALIBRATION_CARD_VERSION,
        marker_id=expected_marker_id,
        applied=True,
        method=NEUTRAL_COLOR_REFERENCE_VERSION,
        rgb_scales=tuple(scales),
        rgb_offsets=tuple(offsets),
        confidence=max(0.0, min(1.0, confidence)),
        suppression_reasons=(),
    )

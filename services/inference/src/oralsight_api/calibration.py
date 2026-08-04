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

CALIBRATION_CARD_VERSION: Final[str] = "oralsight-calibration-v1"
CALIBRATION_DICTIONARY: Final[int] = cv2.aruco.DICT_4X4_50
CALIBRATION_MARKER_ID: Final[int] = 17
CALIBRATION_MARKER_SIDE_MM: Final[float] = 20.0
MIN_MARKER_EDGE_PX: Final[float] = 40.0
MAX_EDGE_VARIATION: Final[float] = 0.22
MAX_TARGET_DISTANCE_MARKER_SIDES: Final[float] = 3.0


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

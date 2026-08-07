"""Gated physical reference-card measurement for queued analysis jobs."""

from __future__ import annotations

from dataclasses import dataclass
from math import hypot
from typing import Final

import cv2
import numpy as np

CARD_VERSION: Final[str] = "oralsight-calibration-v1"
MARKER_ID: Final[int] = 17
MARKER_SIDE_MM: Final[float] = 20.0
CALIBRATION_VERSION: Final[str] = "aruco-4x4-50-same-plane-v1"
MIN_MARKER_EDGE_PX: Final[float] = 40.0
MAX_EDGE_VARIATION: Final[float] = 0.22
MAX_TARGET_DISTANCE_MARKER_SIDES: Final[float] = 3.0


@dataclass(frozen=True, slots=True)
class CalibrationEstimate:
    valid: bool
    marker_id: int | None
    millimeters_per_pixel: float | None
    estimated_width_mm: float | None
    estimated_height_mm: float | None
    estimated_area_mm2: float | None
    confidence: float
    reasons: tuple[str, ...]


def _invalid(
    *reasons: str,
    marker_id: int | None = None,
    confidence: float = 0.0,
) -> CalibrationEstimate:
    return CalibrationEstimate(
        valid=False,
        marker_id=marker_id,
        millimeters_per_pixel=None,
        estimated_width_mm=None,
        estimated_height_mm=None,
        estimated_area_mm2=None,
        confidence=max(0.0, min(1.0, confidence)),
        reasons=tuple(dict.fromkeys(reasons)),
    )


def _candidate_points(
    bounding_box: tuple[float, float, float, float],
    *,
    width: int,
    height: int,
) -> np.ndarray:
    x, y, box_width, box_height = bounding_box
    if (
        not all(np.isfinite(value) for value in bounding_box)
        or min(x, y) < 0
        or box_width <= 0
        or box_height <= 0
        or x + box_width > 1
        or y + box_height > 1
    ):
        raise ValueError("invalid_candidate_bounds")
    return np.asarray(
        [
            [x * width, y * height],
            [(x + box_width) * width, y * height],
            [(x + box_width) * width, (y + box_height) * height],
            [x * width, (y + box_height) * height],
        ],
        dtype=np.float32,
    )


def _candidate_polygon_points(
    polygon: tuple[tuple[float, float], ...],
    *,
    width: int,
    height: int,
) -> np.ndarray:
    if len(polygon) < 3:
        raise ValueError("invalid_candidate_polygon")
    points = np.asarray(polygon, dtype=np.float32)
    if (
        points.shape != (len(polygon), 2)
        or not np.all(np.isfinite(points))
        or np.any(points < 0)
        or np.any(points > 1)
    ):
        raise ValueError("invalid_candidate_polygon")
    points[:, 0] *= width
    points[:, 1] *= height
    if cv2.contourArea(points) <= 0:
        raise ValueError("invalid_candidate_polygon")
    return points


def estimate_calibration(
    encoded_image: bytes,
    *,
    bounding_box: tuple[float, float, float, float] | None,
    candidate_polygon: tuple[tuple[float, float], ...] | None,
    normalized_area: float | None,
    plane_confirmed: bool,
) -> CalibrationEstimate:
    """Return dimensions only after all marker, pose, distance, and plane gates."""

    if not plane_confirmed:
        return _invalid("target_plane_not_confirmed")
    if bounding_box is None or candidate_polygon is None or normalized_area is None:
        return _invalid("candidate_boundary_unavailable")
    if not 0 <= normalized_area <= 1:
        return _invalid("invalid_candidate_area")
    buffer = np.frombuffer(encoded_image, dtype=np.uint8)
    image = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
    if image is None or min(image.shape[:2]) < 64:
        return _invalid("invalid_image")
    height, width = image.shape[:2]
    try:
        target = _candidate_points(bounding_box, width=width, height=height)
        polygon = _candidate_polygon_points(
            candidate_polygon, width=width, height=height
        )
    except ValueError as exc:
        return _invalid(str(exc))

    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    detector = cv2.aruco.ArucoDetector(dictionary, cv2.aruco.DetectorParameters())
    corners, identifiers, _ = detector.detectMarkers(
        cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    )
    if identifiers is None:
        return _invalid("calibration_marker_not_found")
    flat_ids = identifiers.reshape(-1).tolist()
    matches = [index for index, value in enumerate(flat_ids) if value == MARKER_ID]
    if not matches:
        return _invalid(
            "calibration_marker_mismatch",
            marker_id=int(flat_ids[0]) if flat_ids else None,
        )
    marker = np.asarray(corners[matches[0]], dtype=np.float32).reshape(4, 2)
    edge_lengths = np.linalg.norm(np.roll(marker, -1, axis=0) - marker, axis=1)
    mean_edge = float(edge_lengths.mean())
    if not np.isfinite(mean_edge) or mean_edge <= 0:
        return _invalid("calibration_marker_invalid", marker_id=MARKER_ID)
    variation = float(edge_lengths.std() / mean_edge)
    marker_center = marker.mean(axis=0)
    target_center = target.mean(axis=0)
    distance = hypot(
        float(target_center[0] - marker_center[0]),
        float(target_center[1] - marker_center[1]),
    )
    distance_in_sides = distance / mean_edge
    reasons: list[str] = []
    if float(edge_lengths.min()) < MIN_MARKER_EDGE_PX:
        reasons.append("calibration_marker_too_small")
    if variation > MAX_EDGE_VARIATION:
        reasons.append("calibration_marker_pose_unreliable")
    if distance_in_sides > MAX_TARGET_DISTANCE_MARKER_SIDES:
        reasons.append("calibration_marker_too_far_from_target")
    confidence = min(
        1.0,
        mean_edge / 160.0,
        max(0.0, 1.0 - variation / MAX_EDGE_VARIATION),
        max(0.0, 1.0 - distance_in_sides / MAX_TARGET_DISTANCE_MARKER_SIDES),
    )
    if reasons:
        return _invalid(*reasons, marker_id=MARKER_ID, confidence=confidence)

    canonical = np.asarray(
        [
            [0, 0],
            [MARKER_SIDE_MM, 0],
            [MARKER_SIDE_MM, MARKER_SIDE_MM],
            [0, MARKER_SIDE_MM],
        ],
        dtype=np.float32,
    )
    homography = cv2.getPerspectiveTransform(marker, canonical)
    projected = cv2.perspectiveTransform(target.reshape(1, 4, 2), homography)[0]
    projected_polygon = cv2.perspectiveTransform(
        polygon.reshape(1, len(polygon), 2), homography
    )[0]
    estimated_width = float(
        (
            np.linalg.norm(projected[1] - projected[0])
            + np.linalg.norm(projected[2] - projected[3])
        )
        / 2
    )
    estimated_height = float(
        (
            np.linalg.norm(projected[3] - projected[0])
            + np.linalg.norm(projected[2] - projected[1])
        )
        / 2
    )
    millimeters_per_pixel = MARKER_SIDE_MM / mean_edge
    estimated_area = float(abs(cv2.contourArea(projected_polygon)))
    positive_values = (estimated_width, estimated_height, millimeters_per_pixel)
    if (
        not all(np.isfinite(value) and value > 0 for value in positive_values)
        or not np.isfinite(estimated_area)
        or estimated_area < 0
    ):
        return _invalid(
            "calibration_projection_failed", marker_id=MARKER_ID, confidence=confidence
        )
    return CalibrationEstimate(
        valid=True,
        marker_id=MARKER_ID,
        millimeters_per_pixel=millimeters_per_pixel,
        estimated_width_mm=estimated_width,
        estimated_height_mm=estimated_height,
        estimated_area_mm2=estimated_area,
        confidence=confidence,
        reasons=(),
    )

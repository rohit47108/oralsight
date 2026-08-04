from __future__ import annotations

import cv2
import numpy as np
import pytest

from oralsight_api.calibration import (
    CALIBRATION_DICTIONARY,
    CALIBRATION_MARKER_ID,
    estimate_calibrated_bounding_box,
)


def _calibration_scene(*, marker_id: int = CALIBRATION_MARKER_ID) -> np.ndarray:
    image = np.full((600, 800, 3), 255, dtype=np.uint8)
    dictionary = cv2.aruco.getPredefinedDictionary(CALIBRATION_DICTIONARY)
    marker = cv2.aruco.generateImageMarker(dictionary, marker_id, 200)
    image[180:380, 60:260] = cv2.cvtColor(marker, cv2.COLOR_GRAY2BGR)
    return image


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

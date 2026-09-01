from __future__ import annotations

import cv2
import numpy as np
import pytest

from stoma3d_worker.calibration import MARKER_ID, estimate_calibration


def calibration_image(*, marker_id: int = MARKER_ID) -> bytes:
    image = np.full((600, 800, 3), 255, dtype=np.uint8)
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    marker = cv2.aruco.generateImageMarker(dictionary, marker_id, 200)
    image[180:380, 60:260] = cv2.cvtColor(marker, cv2.COLOR_GRAY2BGR)
    ok, encoded = cv2.imencode(".png", image)
    assert ok
    return encoded.tobytes()


def test_valid_same_plane_marker_returns_calibrated_estimates() -> None:
    result = estimate_calibration(
        calibration_image(),
        bounding_box=(360 / 800, 230 / 600, 100 / 800, 50 / 600),
        candidate_polygon=(
            (360 / 800, 230 / 600),
            (460 / 800, 230 / 600),
            (460 / 800, 280 / 600),
            (360 / 800, 280 / 600),
        ),
        normalized_area=5_000 / (800 * 600),
        plane_confirmed=True,
    )

    assert result.valid is True
    assert result.millimeters_per_pixel == pytest.approx(0.1, abs=0.002)
    assert result.estimated_width_mm == pytest.approx(10.0, abs=0.2)
    assert result.estimated_height_mm == pytest.approx(5.0, abs=0.2)
    assert result.estimated_area_mm2 == pytest.approx(50.0, abs=3.0)
    assert result.reasons == ()


@pytest.mark.parametrize(
    ("image", "box", "area", "plane", "reason"),
    [
        (
            calibration_image(),
            (0.45, 0.38, 0.12, 0.08),
            0.01,
            False,
            "target_plane_not_confirmed",
        ),
        (
            calibration_image(marker_id=3),
            (0.45, 0.38, 0.12, 0.08),
            0.01,
            True,
            "calibration_marker_mismatch",
        ),
        (calibration_image(), None, None, True, "candidate_boundary_unavailable"),
        (b"not-an-image", (0.45, 0.38, 0.12, 0.08), 0.01, True, "invalid_image"),
    ],
)
def test_failed_gates_never_return_physical_values(
    image: bytes,
    box: tuple[float, float, float, float] | None,
    area: float | None,
    plane: bool,
    reason: str,
) -> None:
    result = estimate_calibration(
        image,
        bounding_box=box,
        candidate_polygon=(
            (0.45, 0.38),
            (0.57, 0.38),
            (0.57, 0.46),
            (0.45, 0.46),
        ),
        normalized_area=area,
        plane_confirmed=plane,
    )

    assert result.valid is False
    assert reason in result.reasons
    assert result.millimeters_per_pixel is None
    assert result.estimated_width_mm is None
    assert result.estimated_height_mm is None
    assert result.estimated_area_mm2 is None

from __future__ import annotations

import json

import cv2
import numpy as np

from scripts.generate_calibration_cards import (
    CARD_VERSION,
    MARKER_ID,
    NEUTRAL_PATCH_VALUES,
    build_card,
)


def test_generated_card_contains_machine_readable_version_and_marker() -> None:
    card_rgb = np.asarray(build_card(page_width_mm=210.0, page_height_mm=297.0))
    card_bgr = cv2.cvtColor(card_rgb, cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(card_bgr, cv2.COLOR_BGR2GRAY)

    detector = cv2.aruco.ArucoDetector(
        cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    )
    _, marker_ids, _ = detector.detectMarkers(gray)
    qr_payload, qr_points, _ = cv2.QRCodeDetector().detectAndDecode(card_bgr)

    assert marker_ids is not None
    assert marker_ids.reshape(-1).tolist() == [MARKER_ID]
    assert qr_points is not None
    assert json.loads(qr_payload) == {
        "marker_dictionary": "DICT_4X4_50",
        "marker_id": MARKER_ID,
        "marker_side_mm": 20.0,
        "reference_bar_mm": 50.0,
        "schema": "oralsight_calibration_card",
        "version": CARD_VERSION,
    }

    # Geometry is fixed relative to marker 17 so inference can recover all four
    # patch interiors through the marker homography without reading page text.
    marker_corners, _, _ = detector.detectMarkers(gray)
    marker = np.asarray(marker_corners[0], dtype=np.float32).reshape(4, 2)
    marker_side = float(
        np.mean(np.linalg.norm(np.roll(marker, -1, axis=0) - marker, axis=1))
    )
    sampled: list[int] = []
    for index in range(4):
        center_mm = np.asarray(
            [[[38 + index * 11 + 4.5, 6 + 4.5]]],
            dtype=np.float32,
        )
        canonical = np.asarray([[0, 0], [20, 0], [20, 20], [0, 20]], dtype=np.float32)
        transform = cv2.getPerspectiveTransform(canonical, marker)
        center = cv2.perspectiveTransform(center_mm, transform)[0, 0]
        radius = max(2, round(marker_side * 1.5 / 20))
        x, y = round(float(center[0])), round(float(center[1]))
        sampled.append(
            int(np.median(gray[y - radius : y + radius, x - radius : x + radius]))
        )
    assert sampled == list(NEUTRAL_PATCH_VALUES)

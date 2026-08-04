from __future__ import annotations

import json

import cv2
import numpy as np

from scripts.generate_calibration_cards import CARD_VERSION, MARKER_ID, build_card


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

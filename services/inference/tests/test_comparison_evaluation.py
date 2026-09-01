from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from stoma3d_api import comparison_evaluation
from stoma3d_api.contracts import ModelHead, QualityResult
from stoma3d_api.model_adapters import SegmentationPrediction


class _RepeatableSegmentationAdapter:
    head = ModelHead.SEGMENTATION

    def predict(self, _rgb: np.ndarray) -> SegmentationPrediction:
        probabilities = np.full((16, 16), 0.05, dtype=np.float32)
        probabilities[4:12, 4:12] = 0.95
        return SegmentationPrediction(
            probabilities=probabilities,
            threshold=0.5,
            confidence=0.9,
        )


def _accepted_quality(_image: object) -> tuple[QualityResult, float]:
    return (
        QualityResult(
            accepted=True,
            blur_score=0.9,
            exposure_score=0.9,
            glare_score=0.01,
            obstruction_score=0.01,
            face_detected=False,
            reasons=[],
        ),
        0.9,
    )


def _write_image(path: Path) -> None:
    yy, xx = np.mgrid[:256, :256]
    image = np.stack(
        (
            (50 + xx) % 256,
            (70 + yy) % 256,
            (40 + xx + yy) % 256,
        ),
        axis=2,
    ).astype(np.uint8)
    success, encoded = cv2.imencode(".jpg", image)
    assert success
    path.write_bytes(encoded.tobytes())


def _row() -> dict[str, str]:
    return {
        "pair_id": "pair-1",
        "participant_id": "participant-1",
        "split": "test",
        "region": "left_buccal_mucosa",
        "baseline_image_path": "baseline.jpg",
        "current_image_path": "current.jpg",
        "license_status": "approved",
        "audit_status": "approved",
        "consent_scope": "research_evaluation",
        "same_observation_confirmed": "true",
    }


def test_repeat_capture_evaluation_reports_registered_area_error_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_image(tmp_path / "baseline.jpg")
    _write_image(tmp_path / "current.jpg")
    monkeypatch.setattr(comparison_evaluation, "assess_quality", _accepted_quality)
    monkeypatch.setattr(
        comparison_evaluation,
        "_orb_registration",
        lambda _baseline, _current: (
            0.9,
            0.005,
            0.95,
            [],
            np.eye(3, dtype=np.float64),
        ),
    )

    result = comparison_evaluation.evaluate_repeat_capture_rows(
        [_row()],
        data_root=tmp_path,
        segmentation_adapter=_RepeatableSegmentationAdapter(),
    )

    assert result["aggregate_only"] is True
    assert result["evaluable_pair_count"] == 1
    assert result["repeated_capture_area_error"] == pytest.approx(0)
    assert result["gate_passed"] is True
    assert "participant-1" not in str(result)


def test_repeat_capture_evaluation_rejects_paths_outside_controlled_root(
    tmp_path: Path,
) -> None:
    root = tmp_path / "controlled"
    root.mkdir()
    _write_image(root / "current.jpg")
    _write_image(tmp_path / "outside.jpg")
    row = _row()
    row["baseline_image_path"] = "../outside.jpg"

    with pytest.raises(ValueError, match="escapes"):
        comparison_evaluation.evaluate_repeat_capture_rows(
            [row],
            data_root=root,
            segmentation_adapter=_RepeatableSegmentationAdapter(),
        )

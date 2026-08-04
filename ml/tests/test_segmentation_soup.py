from __future__ import annotations

from pathlib import Path

import pytest

from oralsight_ml.segmentation_soup import (
    _build_parser,
    _compatible_configuration,
)


def _source(loss_version: str) -> dict[str, object]:
    return {
        "configuration": {
            "architecture": "presence_gated_unetplusplus_efficientnet_b3",
            "pretrained_imagenet": True,
            "image_size": 384,
            "batch_size": 12,
            "epochs": 30,
            "learning_rate": 0.00036,
            "seed": 20260728,
            "normalization_mean": [0.485, 0.456, 0.406],
            "normalization_std": [0.229, 0.224, 0.225],
            "supplemental_segmentation": None,
            "training_splits": ["train"],
            "segmentation_loss_version": loss_version,
        }
    }


def test_soup_accepts_matching_runs_with_different_losses() -> None:
    configuration = _compatible_configuration(
        _source("tolerant_boundary_v2"),
        _source("tolerant_boundary_presence_v3"),
    )

    assert configuration["image_size"] == 384


def test_soup_rejects_different_initialization_seed() -> None:
    first = _source("tolerant_boundary_v2")
    second = _source("tolerant_boundary_presence_v3")
    second["configuration"]["seed"] = 7  # type: ignore[index]

    with pytest.raises(ValueError, match="seed"):
        _compatible_configuration(first, second)


def test_soup_parser_collects_validation_alphas() -> None:
    args = _build_parser().parse_args(
        [
            "--manifest",
            "segmentation.csv",
            "--data-root",
            "data",
            "--source-a-run",
            "a/run.json",
            "--source-b-run",
            "b/run.json",
            "--output-dir",
            "soup",
            "--alpha",
            "0.4",
            "--alpha",
            "0.6",
        ]
    )

    assert args.source_a_run == Path("a/run.json")
    assert args.alpha == [0.4, 0.6]

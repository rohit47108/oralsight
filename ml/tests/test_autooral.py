from __future__ import annotations

import pytest

from stoma3d_ml.autooral import _build_parser, _normalized_image_number


def test_normalizes_autooral_image_number() -> None:
    assert _normalized_image_number(7) == "0007"
    assert _normalized_image_number("0012") == "0012"


def test_rejects_non_numeric_autooral_image_number() -> None:
    with pytest.raises(ValueError):
        _normalized_image_number("image-7")


def test_autooral_parser_requires_explicit_license_acknowledgements() -> None:
    args = _build_parser().parse_args(
        [
            "--dataset-root",
            "Autooral",
            "--output-manifest",
            "supplement.csv",
            "--archive-sha256",
            "a" * 64,
        ]
    )

    assert args.acknowledge_academic_only_license is False
    assert args.acknowledge_audited_data is False

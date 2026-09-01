"""Evaluate repeat-capture area consistency without retaining image-level output."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from .contracts import ModelHead, MouthRegion
from .model_adapters import ModelAdapter, SegmentationPrediction
from .processing import (
    _orb_registration,
    assess_quality,
    candidate_from_model_mask,
    sanitize_image,
)
from .release_manifest import RELEASE_MANIFEST_ENV, load_release_runtime

REPEAT_CAPTURE_COLUMNS = (
    "pair_id",
    "participant_id",
    "split",
    "region",
    "baseline_image_path",
    "current_image_path",
    "license_status",
    "audit_status",
    "consent_scope",
    "same_observation_confirmed",
)
MAX_REPEATED_CAPTURE_AREA_ERROR = 0.10


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_data_path(data_root: Path, value: str) -> Path:
    root = data_root.resolve(strict=True)
    candidate = (root / value).resolve(strict=True)
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError(
            "A repeat-capture path escapes the controlled data root."
        ) from exc
    if not candidate.is_file():
        raise ValueError("A repeat-capture image path is not a file.")
    return candidate


def load_repeat_capture_manifest(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != REPEAT_CAPTURE_COLUMNS:
            raise ValueError(
                "Repeat-capture manifest columns must exactly match the documented schema."
            )
        rows = [
            {key: (value or "").strip() for key, value in row.items()} for row in reader
        ]
    if not rows:
        raise ValueError("The repeat-capture manifest is empty.")
    return rows


def _validate_rows(rows: Sequence[Mapping[str, str]], data_root: Path) -> None:
    pair_ids: set[str] = set()
    allowed_regions = {region.value for region in MouthRegion}
    for row in rows:
        pair_id = row["pair_id"]
        if not pair_id or pair_id in pair_ids:
            raise ValueError("Repeat-capture pair IDs must be present and unique.")
        pair_ids.add(pair_id)
        if not row["participant_id"]:
            raise ValueError("Every repeat-capture pair requires a participant ID.")
        if row["split"] != "test":
            raise ValueError(
                "Repeat-capture evaluation accepts only the locked test split."
            )
        if row["region"] not in allowed_regions:
            raise ValueError("A repeat-capture row uses an unsupported mouth region.")
        if row["license_status"] != "approved" or row["audit_status"] != "approved":
            raise ValueError(
                "Every repeat-capture row must be license- and audit-approved."
            )
        if row["consent_scope"] not in {
            "research_evaluation",
            "competition_evaluation",
        }:
            raise ValueError(
                "Repeat-capture consent scope does not permit this evaluation."
            )
        if row["same_observation_confirmed"].lower() != "true":
            raise ValueError(
                "Every pair must be manually confirmed as the same unchanged observation."
            )
        _safe_data_path(data_root, row["baseline_image_path"])
        _safe_data_path(data_root, row["current_image_path"])


def _candidate_component(image: Any, adapter: ModelAdapter) -> np.ndarray | None:
    prediction = adapter.predict(image.rgb)
    if not isinstance(prediction, SegmentationPrediction):
        raise ValueError(
            "The released segmentation adapter returned an invalid output."
        )
    _, _, component = candidate_from_model_mask(image, prediction)
    return component


def evaluate_repeat_capture_rows(
    rows: Sequence[Mapping[str, str]],
    *,
    data_root: Path,
    segmentation_adapter: ModelAdapter,
) -> dict[str, object]:
    """Return aggregate-only repeatability evidence for quality-accepted pairs."""

    _validate_rows(rows, data_root)
    errors: list[float] = []
    abstentions: Counter[str] = Counter()
    participants = {row["participant_id"] for row in rows}
    region_counts = Counter(row["region"] for row in rows)

    for row in rows:
        try:
            baseline = sanitize_image(
                _safe_data_path(data_root, row["baseline_image_path"]).read_bytes()
            )
            current = sanitize_image(
                _safe_data_path(data_root, row["current_image_path"]).read_bytes()
            )
            baseline_quality, _ = assess_quality(baseline)
            current_quality, _ = assess_quality(current)
            if not baseline_quality.accepted or not current_quality.accepted:
                abstentions["quality_rejected"] += 1
                continue

            baseline_component = _candidate_component(baseline, segmentation_adapter)
            current_component = _candidate_component(current, segmentation_adapter)
            if baseline_component is None or current_component is None:
                abstentions["candidate_unavailable"] += 1
                continue

            _, _, _, registration_reasons, homography = _orb_registration(
                baseline,
                current,
            )
            if registration_reasons or homography is None:
                abstentions["registration_gate_unmet"] += 1
                continue

            current_height, current_width = current.bgr.shape[:2]
            registered_baseline = cv2.warpPerspective(
                baseline_component,
                homography,
                (current_width, current_height),
                flags=cv2.INTER_NEAREST,
                borderMode=cv2.BORDER_CONSTANT,
                borderValue=0,
            )
            baseline_area = float(np.count_nonzero(registered_baseline))
            current_area = float(np.count_nonzero(current_component))
            if baseline_area <= 0 or current_area <= 0:
                abstentions["candidate_area_zero"] += 1
                continue
            error = abs(current_area - baseline_area) / baseline_area
            if not math.isfinite(error):
                abstentions["non_finite_error"] += 1
                continue
            errors.append(error)
        except (OSError, RuntimeError, ValueError, cv2.error):
            abstentions["evaluation_failed"] += 1

    pair_count = len(rows)
    evaluable_pair_count = len(errors)
    p95_error = (
        float(np.quantile(np.asarray(errors), 0.95, method="higher"))
        if errors
        else None
    )
    return {
        "schema_version": "1.0",
        "evaluated_at": datetime.now(UTC).isoformat(),
        "metric_name": "p95_absolute_relative_registered_area_error",
        "repeated_capture_area_error": p95_error,
        "maximum_allowed_error": MAX_REPEATED_CAPTURE_AREA_ERROR,
        "gate_passed": (
            p95_error is not None and p95_error <= MAX_REPEATED_CAPTURE_AREA_ERROR
        ),
        "pair_count": pair_count,
        "participant_count": len(participants),
        "evaluable_pair_count": evaluable_pair_count,
        "coverage": evaluable_pair_count / pair_count,
        "mean_absolute_relative_error": (float(np.mean(errors)) if errors else None),
        "median_absolute_relative_error": (
            float(np.median(errors)) if errors else None
        ),
        "maximum_absolute_relative_error": max(errors) if errors else None,
        "abstention_counts": dict(sorted(abstentions.items())),
        "region_pair_counts": dict(sorted(region_counts.items())),
        "registration_gates": {
            "minimum_inlier_ratio": 0.60,
            "maximum_reprojection_error_ratio": 0.03,
        },
        "aggregate_only": True,
        "disclaimer": (
            "This result is not a diagnosis. Repeatability evidence does not establish "
            "clinical accuracy or physical measurement validity."
        ),
    }


def _safe_output_path(path: Path) -> Path:
    output = path.resolve(strict=False)
    if output.exists():
        raise ValueError("Refusing to overwrite an existing evaluation artifact.")
    output.parent.mkdir(parents=True, exist_ok=True)
    return output


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pair-manifest", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--release-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--acknowledge-audited-data", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if not args.acknowledge_audited_data:
        print(
            "Evaluation refused: --acknowledge-audited-data is required.",
            file=sys.stderr,
        )
        return 2
    try:
        rows = load_repeat_capture_manifest(args.pair_manifest)
        runtime = load_release_runtime(
            {RELEASE_MANIFEST_ENV: str(args.release_manifest.resolve(strict=True))}
        )
        segmentation_adapter = runtime.adapters.get(ModelHead.SEGMENTATION)
        if segmentation_adapter is None:
            raise ValueError("No verified released segmentation adapter is available.")
        result = evaluate_repeat_capture_rows(
            rows,
            data_root=args.data_root,
            segmentation_adapter=segmentation_adapter,
        )
        result["pair_manifest_sha256"] = _sha256(
            args.pair_manifest.resolve(strict=True)
        )
        result["release_manifest_sha256"] = _sha256(
            args.release_manifest.resolve(strict=True)
        )
        output = _safe_output_path(args.output)
        output.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"Evaluation failed safely: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Fail-closed evaluator for Stoma3D competition model-release thresholds."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .constants import (
    APPEARANCE_CLASSES,
    DISEASE_CLASSES,
    MOUTH_REGIONS,
    RELEASE_THRESHOLDS,
    THRESHOLD_VERSION,
)
from .metrics import wilson_lower_bound

HEADS: tuple[str, ...] = (
    "segmentation",
    "anatomy",
    "appearance",
    "disease",
    "reidentification",
)
SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")
CODE_REVISION_PATTERN = re.compile(r"^[a-f0-9]{40,64}$")


@dataclass(frozen=True)
class GateDecision:
    head: str
    enabled: bool
    reasons: tuple[str, ...]
    observed: Mapping[str, object]
    thresholds: Mapping[str, float | int]

    def as_dict(self) -> dict[str, object]:
        return {
            "head": self.head,
            "enabled": self.enabled,
            "reasons": list(self.reasons),
            "observed": dict(self.observed),
            "thresholds": dict(self.thresholds),
        }


def _evaluation_identity_reasons(payload: Mapping[str, Any]) -> list[str]:
    reasons: list[str] = []
    evaluation_id = payload.get("evaluation_id")
    if not isinstance(evaluation_id, str) or not evaluation_id.strip():
        reasons.append("evaluation_id: non-empty identity is required.")
    for key in ("artifact_sha256", "dataset_manifest_sha256"):
        value = payload.get(key)
        if not isinstance(value, str) or not SHA256_PATTERN.fullmatch(value):
            reasons.append(f"{key}: lowercase SHA-256 digest is required.")
    code_revision = payload.get("code_revision")
    if not isinstance(code_revision, str) or not CODE_REVISION_PATTERN.fullmatch(code_revision):
        reasons.append("code_revision: a 40-64 character lowercase commit digest is required.")
    evaluated_at = payload.get("evaluated_at")
    if not isinstance(evaluated_at, str):
        reasons.append("evaluated_at: timezone-aware RFC 3339 timestamp is required.")
    else:
        try:
            parsed = datetime.fromisoformat(evaluated_at.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                raise ValueError
        except ValueError:
            reasons.append("evaluated_at: timezone-aware RFC 3339 timestamp is required.")
    return reasons


def _section(payload: Mapping[str, Any], key: str, reasons: list[str]) -> Mapping[str, Any]:
    value = payload.get(key)
    if not isinstance(value, Mapping):
        reasons.append(f"{key}: evaluation section is missing or invalid.")
        return {}
    return value


def _number(section: Mapping[str, Any], key: str, reasons: list[str]) -> float | None:
    value = section.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        reasons.append(f"{key}: finite numeric value is required.")
        return None
    converted = float(value)
    if not math.isfinite(converted):
        reasons.append(f"{key}: finite numeric value is required.")
        return None
    return converted


def _integer(section: Mapping[str, Any], key: str, reasons: list[str]) -> int | None:
    value = section.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        reasons.append(f"{key}: non-negative integer is required.")
        return None
    return value


def _require_true(section: Mapping[str, Any], key: str, reasons: list[str]) -> None:
    if section.get(key) is not True:
        reasons.append(f"{key}: must be explicitly true.")


def _minimum(
    section: Mapping[str, Any],
    key: str,
    threshold: float,
    reasons: list[str],
    observed: dict[str, object],
) -> None:
    value = _number(section, key, reasons)
    if value is not None:
        observed[key] = value
        if not 0 <= value <= 1:
            reasons.append(f"{key}: {value:.6g} must be between 0 and 1.")
        elif value < threshold:
            reasons.append(f"{key}: {value:.6g} is below {threshold:.6g}.")


def _maximum(
    section: Mapping[str, Any],
    key: str,
    threshold: float,
    reasons: list[str],
    observed: dict[str, object],
) -> None:
    value = _number(section, key, reasons)
    if value is not None:
        observed[key] = value
        if not 0 <= value <= 1:
            reasons.append(f"{key}: {value:.6g} must be between 0 and 1.")
        elif value > threshold:
            reasons.append(f"{key}: {value:.6g} exceeds {threshold:.6g}.")


def _per_class_minimum(
    section: Mapping[str, Any],
    key: str,
    classes: Sequence[str],
    threshold: float,
    reasons: list[str],
    observed: dict[str, object],
    *,
    integer: bool = False,
) -> None:
    values = section.get(key)
    if not isinstance(values, Mapping):
        reasons.append(f"{key}: complete per-class mapping is required.")
        return
    normalized: dict[str, float | int] = {}
    for label in classes:
        value = values.get(label)
        if integer:
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                reasons.append(f"{key}.{label}: non-negative integer is required.")
                continue
            normalized[label] = value
            if value < threshold:
                reasons.append(f"{key}.{label}: {value} is below {int(threshold)}.")
        else:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                reasons.append(f"{key}.{label}: finite numeric value is required.")
                continue
            converted = float(value)
            if not math.isfinite(converted):
                reasons.append(f"{key}.{label}: finite numeric value is required.")
                continue
            normalized[label] = converted
            if not 0 <= converted <= 1:
                reasons.append(f"{key}.{label}: {converted:.6g} must be between 0 and 1.")
            elif converted < threshold:
                reasons.append(f"{key}.{label}: {converted:.6g} is below {threshold:.6g}.")
    observed[key] = normalized


def _segmentation(payload: Mapping[str, Any]) -> GateDecision:
    reasons: list[str] = []
    observed: dict[str, object] = {}
    section = _section(payload, "segmentation", reasons)
    _require_true(section, "patient_disjoint", reasons)
    thresholds = RELEASE_THRESHOLDS["segmentation"]
    _minimum(section, "dice", float(thresholds["dice"]), reasons, observed)
    _minimum(section, "boundary_f1", float(thresholds["boundary_f1"]), reasons, observed)
    return GateDecision("segmentation", not reasons, tuple(reasons), observed, thresholds)


def _anatomy(payload: Mapping[str, Any]) -> GateDecision:
    reasons: list[str] = []
    observed: dict[str, object] = {}
    section = _section(payload, "anatomy", reasons)
    _require_true(section, "patient_disjoint", reasons)
    thresholds = RELEASE_THRESHOLDS["anatomy"]
    _minimum(section, "macro_f1", float(thresholds["macro_f1"]), reasons, observed)
    _per_class_minimum(
        section,
        "per_class_recall",
        MOUTH_REGIONS,
        float(thresholds["minimum_class_recall"]),
        reasons,
        observed,
    )
    return GateDecision("anatomy", not reasons, tuple(reasons), observed, thresholds)


def _appearance(payload: Mapping[str, Any]) -> GateDecision:
    reasons: list[str] = []
    observed: dict[str, object] = {}
    section = _section(payload, "appearance", reasons)
    _require_true(section, "patient_disjoint", reasons)
    thresholds = RELEASE_THRESHOLDS["appearance"]
    _per_class_minimum(
        section,
        "held_out_patients_per_class",
        APPEARANCE_CLASSES,
        float(thresholds["minimum_patients_per_class"]),
        reasons,
        observed,
        integer=True,
    )
    _minimum(section, "macro_f1", float(thresholds["macro_f1"]), reasons, observed)
    _per_class_minimum(
        section,
        "per_class_recall",
        APPEARANCE_CLASSES,
        float(thresholds["minimum_class_recall"]),
        reasons,
        observed,
    )
    _maximum(
        section,
        "expected_calibration_error",
        float(thresholds["maximum_ece"]),
        reasons,
        observed,
    )
    return GateDecision("appearance", not reasons, tuple(reasons), observed, thresholds)


def _disease(payload: Mapping[str, Any]) -> GateDecision:
    reasons: list[str] = []
    observed: dict[str, object] = {}
    section = _section(payload, "disease", reasons)
    for key in (
        "patient_disjoint",
        "independent_held_out",
        "provenance_complete",
        "clinical_review_signed",
    ):
        _require_true(section, key, reasons)
    thresholds = RELEASE_THRESHOLDS["disease"]
    _per_class_minimum(
        section,
        "held_out_patients_per_class",
        DISEASE_CLASSES,
        float(thresholds["minimum_patients_per_class"]),
        reasons,
        observed,
        integer=True,
    )
    _minimum(section, "macro_f1", float(thresholds["macro_f1"]), reasons, observed)
    _per_class_minimum(
        section,
        "per_class_sensitivity",
        DISEASE_CLASSES,
        float(thresholds["minimum_class_sensitivity"]),
        reasons,
        observed,
    )
    _per_class_minimum(
        section,
        "per_class_specificity",
        DISEASE_CLASSES,
        float(thresholds["minimum_class_specificity"]),
        reasons,
        observed,
    )
    _maximum(
        section,
        "expected_calibration_error",
        float(thresholds["maximum_ece"]),
        reasons,
        observed,
    )
    return GateDecision("disease", not reasons, tuple(reasons), observed, thresholds)


def _reidentification(payload: Mapping[str, Any]) -> GateDecision:
    reasons: list[str] = []
    observed: dict[str, object] = {}
    section = _section(payload, "reidentification", reasons)
    _require_true(section, "patient_disjoint", reasons)
    _require_true(section, "user_confirmation_required", reasons)
    thresholds = RELEASE_THRESHOLDS["reidentification"]

    pair_counts: dict[str, int] = {}
    for key, threshold_key in (
        ("matched_pairs", "minimum_matched_pairs"),
        ("hard_negative_pairs", "minimum_hard_negative_pairs"),
        ("held_out_patients", "minimum_patients"),
    ):
        value = _integer(section, key, reasons)
        if value is not None:
            pair_counts[key] = value
            observed[key] = value
            threshold = int(thresholds[threshold_key])
            if value < threshold:
                reasons.append(f"{key}: {value} is below {threshold}.")

    true_positives = _integer(section, "true_positive_matches", reasons)
    false_positives = _integer(section, "false_positive_matches", reasons)
    if true_positives is not None and false_positives is not None:
        if true_positives > pair_counts.get("matched_pairs", -1):
            reasons.append("true_positive_matches: cannot exceed the evaluated matched pairs.")
        if false_positives > pair_counts.get("hard_negative_pairs", -1):
            reasons.append(
                "false_positive_matches: cannot exceed the evaluated hard-negative pairs."
            )
        predicted_positive = true_positives + false_positives
        if predicted_positive == 0:
            reasons.append("precision: at least one predicted match is required.")
        else:
            precision = true_positives / predicted_positive
            lower = wilson_lower_bound(true_positives, predicted_positive)
            observed["precision"] = precision
            observed["precision_lower_95"] = lower
            if precision < float(thresholds["precision"]):
                reasons.append(
                    f"precision: {precision:.6g} is below {float(thresholds['precision']):.6g}."
                )
            if lower < float(thresholds["precision_lower_95"]):
                reasons.append(
                    "precision_lower_95: "
                    f"{lower:.6g} is below {float(thresholds['precision_lower_95']):.6g}."
                )
    return GateDecision("reidentification", not reasons, tuple(reasons), observed, thresholds)


def evaluate_release_gates(payload: Mapping[str, Any]) -> dict[str, object]:
    """Evaluate all heads; missing, malformed, or borderline evidence disables that head."""

    decisions = (
        _segmentation(payload),
        _anatomy(payload),
        _appearance(payload),
        _disease(payload),
        _reidentification(payload),
    )
    identity_reasons = _evaluation_identity_reasons(payload)
    if identity_reasons:
        decisions = tuple(
            GateDecision(
                decision.head,
                False,
                tuple(identity_reasons) + decision.reasons,
                decision.observed,
                decision.thresholds,
            )
            for decision in decisions
        )
    return {
        "schema_version": "1.0",
        "threshold_version": THRESHOLD_VERSION,
        "evaluation_id": str(payload.get("evaluation_id", "unspecified")),
        "artifact_sha256": payload.get("artifact_sha256"),
        "dataset_manifest_sha256": payload.get("dataset_manifest_sha256"),
        "code_revision": payload.get("code_revision"),
        "evaluated_at": payload.get("evaluated_at"),
        "disclaimer": "This result is not a diagnosis. Gate passage is not clinical validation.",
        "heads": {decision.head: decision.as_dict() for decision in decisions},
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evaluation", type=Path, help="Aggregate evaluation JSON; never images.")
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--require",
        action="append",
        choices=HEADS,
        default=[],
        help="Exit 1 when the named head is disabled; repeat for multiple heads.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        raw = json.loads(args.evaluation.read_text(encoding="utf-8"))
        if not isinstance(raw, Mapping):
            raise ValueError("Evaluation JSON must be an object.")
        report = evaluate_release_gates(raw)
        encoded = json.dumps(report, indent=2, sort_keys=True) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(encoded, encoding="utf-8")
        else:
            print(encoded, end="")
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        print(f"Gate evaluation failed: {exc}", file=sys.stderr)
        return 2

    heads = report["heads"]
    assert isinstance(heads, dict)
    return 1 if any(not bool(heads[name]["enabled"]) for name in args.require) else 0


if __name__ == "__main__":
    sys.exit(main())

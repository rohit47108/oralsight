"""Dependency-free metrics used by release-gate and subgroup evaluations."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence


def _require_probability(value: float, name: str) -> None:
    if not math.isfinite(value) or not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must be a finite probability in [0, 1], got {value!r}.")


def expected_calibration_error(
    confidences: Sequence[float], correct: Sequence[bool], *, bins: int = 10
) -> float:
    """Return equal-width expected calibration error for confidence predictions."""

    if len(confidences) != len(correct):
        raise ValueError("confidences and correct must have equal lengths.")
    if not confidences:
        raise ValueError("At least one prediction is required.")
    if bins < 1:
        raise ValueError("bins must be positive.")
    for confidence in confidences:
        _require_probability(float(confidence), "confidence")

    total = len(confidences)
    result = 0.0
    for bin_index in range(bins):
        lower = bin_index / bins
        upper = (bin_index + 1) / bins
        indices = [
            index
            for index, confidence in enumerate(confidences)
            if confidence >= lower and (confidence < upper or bin_index == bins - 1)
        ]
        if not indices:
            continue
        accuracy = sum(1.0 if correct[index] else 0.0 for index in indices) / len(indices)
        mean_confidence = sum(float(confidences[index]) for index in indices) / len(indices)
        result += (len(indices) / total) * abs(accuracy - mean_confidence)
    return result


def multiclass_calibration_metrics(
    y_true: Sequence[str],
    probabilities: Sequence[Mapping[str, float]],
    labels: Sequence[str],
    *,
    bins: int = 10,
) -> dict[str, float | int]:
    """Compute confidence ECE and multiclass Brier score from calibrated probabilities."""

    if len(y_true) != len(probabilities):
        raise ValueError("y_true and probabilities must have equal lengths.")
    if not y_true:
        raise ValueError("At least one prediction is required.")
    if len(set(labels)) != len(labels) or not labels:
        raise ValueError("labels must be a non-empty unique sequence.")

    label_set = set(labels)
    confidences: list[float] = []
    correct: list[bool] = []
    brier_total = 0.0
    for expected, distribution in zip(y_true, probabilities, strict=True):
        if expected not in label_set:
            raise ValueError(f"Unknown true label: {expected!r}.")
        if set(distribution) != label_set:
            raise ValueError("Each probability mapping must contain exactly the configured labels.")
        values = {label: float(distribution[label]) for label in labels}
        for label, value in values.items():
            _require_probability(value, f"probability[{label}]")
        if not math.isclose(sum(values.values()), 1.0, abs_tol=1e-6):
            raise ValueError("Class probabilities must sum to 1 within 1e-6.")
        predicted = max(labels, key=lambda label: values[label])
        confidence = values[predicted]
        confidences.append(confidence)
        correct.append(predicted == expected)
        brier_total += sum(
            (values[label] - (1.0 if label == expected else 0.0)) ** 2 for label in labels
        )

    return {
        "expected_calibration_error": expected_calibration_error(confidences, correct, bins=bins),
        "multiclass_brier_score": brier_total / len(y_true),
        "sample_count": len(y_true),
    }


def classification_metrics(
    y_true: Sequence[str], y_pred: Sequence[str], labels: Sequence[str]
) -> dict[str, object]:
    """Compute confusion-derived metrics with explicit zero-division behavior."""

    if len(y_true) != len(y_pred):
        raise ValueError("y_true and y_pred must have equal lengths.")
    if not y_true:
        raise ValueError("At least one prediction is required.")
    if len(set(labels)) != len(labels) or not labels:
        raise ValueError("labels must be a non-empty unique sequence.")

    label_set = set(labels)
    if any(value not in label_set for value in (*y_true, *y_pred)):
        raise ValueError("All true and predicted labels must be in labels.")

    support: dict[str, int] = {}
    precision: dict[str, float] = {}
    recall: dict[str, float] = {}
    specificity: dict[str, float] = {}
    f1: dict[str, float] = {}
    total = len(y_true)
    for label in labels:
        true_positive = sum(
            1
            for expected, predicted in zip(y_true, y_pred, strict=True)
            if expected == predicted == label
        )
        false_positive = sum(
            1
            for expected, predicted in zip(y_true, y_pred, strict=True)
            if expected != label and predicted == label
        )
        false_negative = sum(
            1
            for expected, predicted in zip(y_true, y_pred, strict=True)
            if expected == label and predicted != label
        )
        true_negative = total - true_positive - false_positive - false_negative
        support[label] = true_positive + false_negative
        precision[label] = (
            true_positive / (true_positive + false_positive)
            if true_positive + false_positive
            else 0.0
        )
        recall[label] = (
            true_positive / (true_positive + false_negative)
            if true_positive + false_negative
            else 0.0
        )
        specificity[label] = (
            true_negative / (true_negative + false_positive)
            if true_negative + false_positive
            else 0.0
        )
        denominator = precision[label] + recall[label]
        f1[label] = 2 * precision[label] * recall[label] / denominator if denominator else 0.0

    return {
        "sample_count": total,
        "accuracy": sum(
            1 for expected, predicted in zip(y_true, y_pred, strict=True) if expected == predicted
        )
        / total,
        "macro_f1": sum(f1.values()) / len(labels),
        "per_class_support": support,
        "per_class_precision": precision,
        "per_class_recall": recall,
        "per_class_specificity": specificity,
        "per_class_f1": f1,
    }


def wilson_lower_bound(successes: int, total: int, *, z: float = 1.959963984540054) -> float:
    """Lower bound of a two-sided 95% Wilson score interval by default."""

    if total <= 0:
        raise ValueError("total must be positive.")
    if successes < 0 or successes > total:
        raise ValueError("successes must be between zero and total.")
    if z <= 0 or not math.isfinite(z):
        raise ValueError("z must be positive and finite.")
    proportion = successes / total
    z_squared = z * z
    denominator = 1 + z_squared / total
    center = proportion + z_squared / (2 * total)
    spread = z * math.sqrt((proportion * (1 - proportion) + z_squared / (4 * total)) / total)
    return (center - spread) / denominator


def mean_finite(values: Sequence[float], *, name: str) -> float:
    if not values:
        raise ValueError(f"{name} requires at least one value.")
    converted = [float(value) for value in values]
    if any(not math.isfinite(value) for value in converted):
        raise ValueError(f"{name} contains a non-finite value.")
    return sum(converted) / len(converted)

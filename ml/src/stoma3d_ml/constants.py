"""Canonical taxonomies and release thresholds shared by evaluation utilities."""

from __future__ import annotations

from typing import Final

MOUTH_REGIONS: Final[tuple[str, ...]] = (
    "dorsal_tongue",
    "ventral_tongue",
    "left_buccal_mucosa",
    "right_buccal_mucosa",
    "upper_lip",
    "lower_lip",
    "upper_dental_arch",
    "lower_dental_arch",
)

APPEARANCE_CLASSES: Final[tuple[str, ...]] = (
    "red-patch",
    "white-patch",
    "ulcer-like",
    "mixed",
    "pigmented",
    "none-detected",
    "unsupported",
)

DISEASE_CLASSES: Final[tuple[str, ...]] = (
    "normal",
    "variation",
    "opmd",
    "oral_cancer",
)

SPLITS: Final[tuple[str, ...]] = ("train", "validation", "test", "external_test")
TRAINING_CONSENT_SCOPES: Final[frozenset[str]] = frozenset({"research_training"})
EVALUATION_CONSENT_SCOPES: Final[frozenset[str]] = frozenset(
    {"research_training", "evaluation_only"}
)
ALL_CONSENT_SCOPES: Final[frozenset[str]] = frozenset(
    {"research_training", "evaluation_only", "synthetic_demo"}
)

THRESHOLD_VERSION: Final[str] = "2026.1"

RELEASE_THRESHOLDS: Final[dict[str, dict[str, float | int]]] = {
    "segmentation": {"dice": 0.70, "boundary_f1": 0.60},
    "anatomy": {"macro_f1": 0.80, "minimum_class_recall": 0.70},
    "appearance": {
        "minimum_patients_per_class": 50,
        "macro_f1": 0.75,
        "minimum_class_recall": 0.70,
        "maximum_ece": 0.08,
    },
    "disease": {
        "minimum_patients_per_class": 100,
        "macro_f1": 0.80,
        "minimum_class_sensitivity": 0.80,
        "minimum_class_specificity": 0.80,
        "maximum_ece": 0.05,
    },
    "reidentification": {
        "minimum_matched_pairs": 200,
        "minimum_hard_negative_pairs": 200,
        "minimum_patients": 50,
        "precision": 0.95,
        "precision_lower_95": 0.90,
    },
}

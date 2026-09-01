from __future__ import annotations

from copy import deepcopy

from stoma3d_ml.constants import APPEARANCE_CLASSES, DISEASE_CLASSES, MOUTH_REGIONS


def manifest_row(**overrides: str) -> dict[str, str]:
    row = {
        "sample_id": "sample-1",
        "patient_id": "patient-alpha",
        "split": "train",
        "region": "dorsal_tongue",
        "image_path": "images/sample-1.jpg",
        "mask_path": "masks/sample-1.png",
        "lesion_id": "lesion-alpha",
        "anatomy_label": "dorsal_tongue",
        "appearance_label": "red-patch",
        "disease_label": "normal",
        "device_family": "synthetic-device",
        "source_dataset": "synthetic-test-only",
        "license_status": "approved",
        "audit_status": "approved",
        "consent_scope": "research_training",
    }
    row.update(overrides)
    return row


def passing_evaluation() -> dict[str, object]:
    return {
        "evaluation_id": "synthetic-threshold-test",
        "artifact_sha256": "a" * 64,
        "dataset_manifest_sha256": "b" * 64,
        "code_revision": "c" * 40,
        "evaluated_at": "2026-07-21T12:00:00Z",
        "segmentation": {
            "patient_disjoint": True,
            "dice": 0.70,
            "boundary_f1": 0.60,
        },
        "anatomy": {
            "patient_disjoint": True,
            "macro_f1": 0.80,
            "per_class_recall": {label: 0.70 for label in MOUTH_REGIONS},
        },
        "appearance": {
            "patient_disjoint": True,
            "held_out_patients_per_class": {label: 50 for label in APPEARANCE_CLASSES},
            "macro_f1": 0.75,
            "per_class_recall": {label: 0.70 for label in APPEARANCE_CLASSES},
            "expected_calibration_error": 0.08,
        },
        "disease": {
            "patient_disjoint": True,
            "independent_held_out": True,
            "provenance_complete": True,
            "clinical_review_signed": True,
            "held_out_patients_per_class": {label: 100 for label in DISEASE_CLASSES},
            "macro_f1": 0.80,
            "per_class_sensitivity": {label: 0.80 for label in DISEASE_CLASSES},
            "per_class_specificity": {label: 0.80 for label in DISEASE_CLASSES},
            "expected_calibration_error": 0.05,
        },
        "reidentification": {
            "patient_disjoint": True,
            "user_confirmation_required": True,
            "matched_pairs": 400,
            "hard_negative_pairs": 400,
            "held_out_patients": 60,
            "true_positive_matches": 390,
            "false_positive_matches": 10,
        },
    }


def copied_passing_evaluation() -> dict[str, object]:
    return deepcopy(passing_evaluation())

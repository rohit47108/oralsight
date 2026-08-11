from __future__ import annotations

from oralsight_ml.fresh_holdout import create_fresh_holdout
from oralsight_ml.manifest import REQUIRED_COLUMNS


def _row(patient: str, split: str, label: str, index: int) -> dict[str, str]:
    row = {column: "" for column in REQUIRED_COLUMNS}
    row.update(
        {
            "sample_id": f"sample-{index}",
            "patient_id": patient,
            "split": split,
            "region": "dorsal_tongue",
            "image_path": f"images/{index}.jpg",
            "mask_path": f"masks/{index}.png",
            "anatomy_label": "dorsal_tongue",
            "disease_label": label,
            "device_family": "mixed",
            "source_dataset": "test",
            "license_status": "approved",
            "audit_status": "approved",
            "consent_scope": "research_training",
        }
    )
    return row


def test_fresh_holdout_is_deterministic_and_excludes_prior_holdouts() -> None:
    rows: list[dict[str, str]] = []
    index = 0
    prior_holdout: set[str] = set()
    for label in ("normal", "variation", "opmd", "oral_cancer"):
        for number in range(6):
            patient = f"{label}-train-{number}"
            rows.append(_row(patient, "train", label, index))
            index += 1
        for split in ("validation", "test"):
            patient = f"{label}-{split}"
            prior_holdout.add(patient)
            rows.append(_row(patient, split, label, index))
            index += 1

    first, provenance = create_fresh_holdout(rows, seed="fresh-v1")
    second, second_provenance = create_fresh_holdout(rows, seed="fresh-v1")
    first_assignments = {row["patient_id"]: row["split"] for row in first}
    second_assignments = {row["patient_id"]: row["split"] for row in second}

    assert first_assignments == second_assignments
    assert (
        not {
            patient
            for patient, split in first_assignments.items()
            if split in {"validation", "test"}
        }
        & prior_holdout
    )
    assert provenance["patient_assignment_sha256"] == second_provenance["patient_assignment_sha256"]
    assert provenance["split_patient_counts"] == {
        "test": 4,
        "train": 24,
        "validation": 4,
    }


def test_fresh_holdout_preserves_multirow_patient_assignment() -> None:
    rows = [
        _row("normal-train", "train", "normal", 1),
        _row("normal-train", "train", "variation", 2),
        _row("normal-validation", "validation", "normal", 3),
        _row("normal-test", "test", "normal", 4),
        _row("other-train", "train", "normal", 5),
        _row("third-train", "train", "normal", 6),
    ]

    output, _ = create_fresh_holdout(rows, seed="multirow")
    assigned = {row["split"] for row in output if row["patient_id"] == "normal-train"}

    assert len(assigned) == 1


def test_fresh_holdout_excludes_every_previously_evaluated_patient() -> None:
    rows: list[dict[str, str]] = []
    index = 0
    for label in ("normal", "variation", "opmd", "oral_cancer"):
        for number in range(8):
            rows.append(_row(f"{label}-train-{number}", "train", label, index))
            index += 1
        rows.append(_row(f"{label}-validation", "validation", label, index))
        index += 1
        rows.append(_row(f"{label}-test", "test", label, index))
        index += 1
    excluded = {f"{label}-train-0" for label in ("normal", "variation", "opmd", "oral_cancer")}

    output, provenance = create_fresh_holdout(
        rows,
        seed="fresh-after-failed-test",
        excluded_holdout_patient_ids=excluded,
    )

    selected = {row["patient_id"] for row in output if row["split"] in {"validation", "test"}}
    assert not selected & excluded
    assert provenance["previously_evaluated_holdout_patient_count_excluded"] == 4

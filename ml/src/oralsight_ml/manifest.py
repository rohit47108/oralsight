"""Patient-disjoint manifest validation with audited-data enforcement."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath

from .constants import (
    ALL_CONSENT_SCOPES,
    APPEARANCE_CLASSES,
    DISEASE_CLASSES,
    EVALUATION_CONSENT_SCOPES,
    MOUTH_REGIONS,
    SPLITS,
    TRAINING_CONSENT_SCOPES,
)

REQUIRED_COLUMNS: tuple[str, ...] = (
    "sample_id",
    "patient_id",
    "split",
    "region",
    "image_path",
    "mask_path",
    "lesion_id",
    "anatomy_label",
    "appearance_label",
    "disease_label",
    "device_family",
    "source_dataset",
    "license_status",
    "audit_status",
    "consent_scope",
)


@dataclass(frozen=True)
class ManifestIssue:
    code: str
    message: str
    row: int | None = None

    def as_dict(self) -> dict[str, str | int]:
        result: dict[str, str | int] = {"code": self.code, "message": self.message}
        if self.row is not None:
            result["row"] = self.row
        return result


@dataclass(frozen=True)
class ManifestReport:
    valid: bool
    row_count: int
    patient_count: int
    split_patient_counts: Mapping[str, int]
    issues: tuple[ManifestIssue, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "valid": self.valid,
            "row_count": self.row_count,
            "patient_count": self.patient_count,
            "split_patient_counts": dict(self.split_patient_counts),
            "issues": [issue.as_dict() for issue in self.issues],
        }


def load_manifest(path: Path) -> tuple[list[dict[str, str]], list[ManifestIssue]]:
    """Load a CSV manifest without resolving or reading any referenced images."""

    if not path.is_file():
        return [], [ManifestIssue("manifest_not_found", f"Manifest not found: {path}")]

    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            fieldnames = tuple(reader.fieldnames or ())
            missing = [column for column in REQUIRED_COLUMNS if column not in fieldnames]
            if missing:
                return [], [
                    ManifestIssue(
                        "missing_columns", "Missing required columns: " + ", ".join(missing)
                    )
                ]
            rows = [
                {key: (value or "").strip() for key, value in row.items() if key is not None}
                for row in reader
            ]
            return rows, []
    except (OSError, UnicodeError, csv.Error) as exc:
        return [], [ManifestIssue("manifest_unreadable", str(exc))]


def _is_safe_relative_path(value: str) -> bool:
    if not value:
        return False
    posix = PurePosixPath(value.replace("\\", "/"))
    windows = PureWindowsPath(value)
    return (
        not posix.is_absolute()
        and not windows.is_absolute()
        and windows.drive == ""
        and ".." not in posix.parts
        and not value.startswith(("http://", "https://", "s3://", "gs://"))
    )


def resolve_data_path(data_root: Path, relative_path: str) -> Path:
    """Resolve a manifest path and guarantee it remains beneath ``data_root``."""

    if not _is_safe_relative_path(relative_path):
        raise ValueError(f"Unsafe or non-relative data path: {relative_path!r}")
    root = data_root.resolve(strict=False)
    candidate = (root / Path(relative_path.replace("/", str(Path("/"))))).resolve(strict=False)
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"Data path escapes configured root: {relative_path!r}") from exc
    return candidate


def validate_manifest(
    rows: Sequence[Mapping[str, str]],
    *,
    require_audited: bool = False,
    require_files: bool = False,
    data_root: Path | None = None,
    task: str | None = None,
) -> ManifestReport:
    """Validate schema values, paths, audit state, and patient-level split isolation."""

    issues: list[ManifestIssue] = []
    seen_samples: dict[str, int] = {}
    patient_splits: dict[tuple[str, str], set[str]] = {}
    split_patients: dict[str, set[tuple[str, str]]] = {split: set() for split in SPLITS}

    if not rows:
        issues.append(ManifestIssue("empty_manifest", "Manifest contains no sample rows."))

    if require_files and data_root is None:
        issues.append(
            ManifestIssue(
                "missing_data_root", "A data root is required when file checks are enabled."
            )
        )

    for index, row in enumerate(rows, start=2):
        sample_id = row.get("sample_id", "").strip()
        patient_id = row.get("patient_id", "").strip()
        source = row.get("source_dataset", "").strip()
        split = row.get("split", "").strip()
        region = row.get("region", "").strip()

        for required_value in ("sample_id", "patient_id", "source_dataset", "device_family"):
            if not row.get(required_value, "").strip():
                issues.append(
                    ManifestIssue("missing_value", f"{required_value} must not be blank.", index)
                )

        if sample_id:
            if sample_id in seen_samples:
                issues.append(
                    ManifestIssue(
                        "duplicate_sample_id",
                        f"sample_id {sample_id!r} also appears on row {seen_samples[sample_id]}.",
                        index,
                    )
                )
            else:
                seen_samples[sample_id] = index

        if split not in SPLITS:
            issues.append(
                ManifestIssue("invalid_split", f"split must be one of {', '.join(SPLITS)}.", index)
            )
        if region not in MOUTH_REGIONS:
            issues.append(
                ManifestIssue(
                    "invalid_region", f"region must be one of {', '.join(MOUTH_REGIONS)}.", index
                )
            )

        identity = (source, patient_id)
        if source and patient_id and split in SPLITS:
            patient_splits.setdefault(identity, set()).add(split)
            split_patients[split].add(identity)

        consent_scope = row.get("consent_scope", "").strip()
        if consent_scope not in ALL_CONSENT_SCOPES:
            issues.append(
                ManifestIssue(
                    "invalid_consent_scope",
                    f"consent_scope must be one of {', '.join(sorted(ALL_CONSENT_SCOPES))}.",
                    index,
                )
            )
        elif split == "train" and consent_scope not in TRAINING_CONSENT_SCOPES:
            issues.append(
                ManifestIssue(
                    "training_not_consented",
                    "Training rows require consent_scope=research_training.",
                    index,
                )
            )
        elif split in {"validation", "test", "external_test"} and (
            consent_scope not in EVALUATION_CONSENT_SCOPES
        ):
            issues.append(
                ManifestIssue(
                    "evaluation_not_consented",
                    "Held-out rows require research_training or evaluation_only consent scope.",
                    index,
                )
            )

        if require_audited:
            if row.get("license_status", "").strip() != "approved":
                issues.append(
                    ManifestIssue("license_not_approved", "license_status must be approved.", index)
                )
            if row.get("audit_status", "").strip() != "approved":
                issues.append(
                    ManifestIssue("data_not_audited", "audit_status must be approved.", index)
                )

        image_path = row.get("image_path", "").strip()
        if not _is_safe_relative_path(image_path):
            issues.append(
                ManifestIssue(
                    "unsafe_image_path", "image_path must be a safe relative local path.", index
                )
            )
        elif (
            require_files
            and data_root is not None
            and not resolve_data_path(data_root, image_path).is_file()
        ):
            issues.append(
                ManifestIssue(
                    "image_not_found",
                    "Referenced image file was not found.",
                    index,
                )
            )

        issues.extend(_validate_task_row(row, index, task, require_files, data_root))

    for identity, splits in patient_splits.items():
        if len(splits) > 1:
            source, patient_id = identity
            issues.append(
                ManifestIssue(
                    "patient_split_leakage",
                    (
                        f"Patient {source}:{patient_id} occurs in multiple splits: "
                        f"{', '.join(sorted(splits))}."
                    ),
                )
            )

    return ManifestReport(
        valid=not issues,
        row_count=len(rows),
        patient_count=len(patient_splits),
        split_patient_counts={split: len(patients) for split, patients in split_patients.items()},
        issues=tuple(issues),
    )


def _validate_task_row(
    row: Mapping[str, str],
    row_number: int,
    task: str | None,
    require_files: bool,
    data_root: Path | None,
) -> Iterable[ManifestIssue]:
    if task is None:
        return ()

    issues: list[ManifestIssue] = []
    label_field: str | None = None
    allowed_labels: tuple[str, ...] = ()
    if task == "anatomy":
        label_field, allowed_labels = "anatomy_label", MOUTH_REGIONS
    elif task == "appearance":
        label_field, allowed_labels = "appearance_label", APPEARANCE_CLASSES
    elif task == "disease":
        label_field, allowed_labels = "disease_label", DISEASE_CLASSES
    elif task == "segmentation":
        mask_path = row.get("mask_path", "").strip()
        if not _is_safe_relative_path(mask_path):
            issues.append(
                ManifestIssue(
                    "unsafe_mask_path",
                    "Segmentation rows require a safe relative mask_path.",
                    row_number,
                )
            )
        elif (
            require_files
            and data_root is not None
            and not resolve_data_path(data_root, mask_path).is_file()
        ):
            issues.append(
                ManifestIssue(
                    "mask_not_found",
                    "Referenced mask file was not found.",
                    row_number,
                )
            )
    elif task == "reidentification":
        if not row.get("lesion_id", "").strip():
            issues.append(
                ManifestIssue(
                    "missing_lesion_id", "Re-identification rows require lesion_id.", row_number
                )
            )
    else:
        issues.append(ManifestIssue("invalid_task", f"Unknown task: {task}.", row_number))

    if label_field is not None:
        value = row.get(label_field, "").strip()
        if value not in allowed_labels:
            issues.append(
                ManifestIssue(
                    "invalid_task_label",
                    f"{label_field} must be one of {', '.join(allowed_labels)} for {task}.",
                    row_number,
                )
            )
    return tuple(issues)


def validate_manifest_path(
    path: Path,
    *,
    require_audited: bool = False,
    require_files: bool = False,
    data_root: Path | None = None,
    task: str | None = None,
) -> ManifestReport:
    rows, load_issues = load_manifest(path)
    if load_issues:
        return ManifestReport(False, 0, 0, {}, tuple(load_issues))
    return validate_manifest(
        rows,
        require_audited=require_audited,
        require_files=require_files,
        data_root=data_root,
        task=task,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--require-audited", action="store_true")
    parser.add_argument("--require-files", action="store_true")
    parser.add_argument("--data-root", type=Path)
    parser.add_argument(
        "--task", choices=("segmentation", "anatomy", "appearance", "disease", "reidentification")
    )
    parser.add_argument("--output", type=Path, help="Optional aggregate JSON report path.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    report = validate_manifest_path(
        args.manifest,
        require_audited=args.require_audited,
        require_files=args.require_files,
        data_root=args.data_root,
        task=args.task,
    )
    payload = json.dumps(report.as_dict(), indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)
    return 0 if report.valid else 2


if __name__ == "__main__":
    sys.exit(main())

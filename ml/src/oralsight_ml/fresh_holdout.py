"""Create a deterministic fresh patient holdout from a prior training pool.

This tool is for a replacement engineering evaluation after an earlier holdout has
already influenced model development. It never reads image bytes. Patient identifiers
remain only in the controlled input and output manifests; the provenance file contains
counts and digests, not identifiers.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path

from .manifest import REQUIRED_COLUMNS, load_manifest

SEVERITY = {
    "normal": 0,
    "variation": 1,
    "opmd": 2,
    "oral_cancer": 3,
}
SPLITS = ("train", "validation", "test")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _patient_state(
    rows: Sequence[Mapping[str, str]],
) -> tuple[dict[str, str], dict[str, str]]:
    splits: dict[str, str] = {}
    labels: dict[str, str] = {}
    for row in rows:
        patient_id = row["patient_id"]
        split = row["split"]
        label = row["disease_label"]
        if split not in SPLITS:
            raise ValueError(f"Unsupported source split: {split!r}")
        previous_split = splits.setdefault(patient_id, split)
        if previous_split != split:
            raise ValueError("The source manifest is not patient-disjoint.")
        if label not in SEVERITY:
            raise ValueError(f"Unsupported disease stratum: {label!r}")
        previous_label = labels.get(patient_id)
        if previous_label is None or SEVERITY[label] > SEVERITY[previous_label]:
            labels[patient_id] = label
    return splits, labels


def _stable_order(patient_ids: Sequence[str], *, seed: str, stratum: str) -> list[str]:
    return sorted(
        patient_ids,
        key=lambda patient_id: hashlib.sha256(
            f"{seed}:{stratum}:{patient_id}".encode()
        ).hexdigest(),
    )


def create_fresh_holdout(
    rows: Sequence[Mapping[str, str]],
    *,
    seed: str,
    excluded_holdout_patient_ids: set[str] | None = None,
) -> tuple[list[dict[str, str]], dict[str, object]]:
    if not seed or len(seed) > 128:
        raise ValueError("The split seed must contain 1 to 128 characters.")
    source_splits, labels = _patient_state(rows)
    original_counts: dict[str, Counter[str]] = {
        split: Counter(
            labels[patient_id]
            for patient_id, patient_split in source_splits.items()
            if patient_split == split
        )
        for split in SPLITS
    }
    excluded = excluded_holdout_patient_ids or set()
    unknown_exclusions = excluded - set(source_splits)
    if unknown_exclusions:
        raise ValueError("An excluded holdout contains patients outside the source manifest.")
    eligible: dict[str, list[str]] = defaultdict(list)
    for patient_id, split in source_splits.items():
        if split == "train" and patient_id not in excluded:
            eligible[labels[patient_id]].append(patient_id)

    assignments = {patient_id: "train" for patient_id in source_splits}
    selected: set[str] = set()
    target_counts: dict[str, dict[str, int]] = {"test": {}, "validation": {}}
    for stratum in SEVERITY:
        ordered = _stable_order(eligible[stratum], seed=seed, stratum=stratum)
        test_count = original_counts["test"][stratum]
        validation_count = original_counts["validation"][stratum]
        required = test_count + validation_count
        if len(ordered) < required:
            raise ValueError(
                f"Not enough prior-training patients in {stratum!r} for fresh holdouts."
            )
        test_patients = ordered[:test_count]
        validation_patients = ordered[test_count:required]
        for patient_id in test_patients:
            assignments[patient_id] = "test"
        for patient_id in validation_patients:
            assignments[patient_id] = "validation"
        selected.update(test_patients)
        selected.update(validation_patients)
        target_counts["test"][stratum] = test_count
        target_counts["validation"][stratum] = validation_count

    prior_holdout = {
        patient_id for patient_id, split in source_splits.items() if split in {"validation", "test"}
    }
    if selected & prior_holdout:
        raise RuntimeError("A fresh holdout contains a prior held-out patient.")

    output_rows = [{**dict(row), "split": assignments[row["patient_id"]]} for row in rows]
    output_rows.sort(key=lambda row: (row["split"], row["sample_id"]))
    output_splits, output_labels = _patient_state(output_rows)
    split_counts = Counter(output_splits.values())
    assignment_digest = hashlib.sha256(
        "\n".join(
            f"{patient_id}:{output_splits[patient_id]}" for patient_id in sorted(output_splits)
        ).encode()
    ).hexdigest()
    provenance: dict[str, object] = {
        "schema_version": "1.0",
        "created_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "algorithm": "sha256_stratified_fresh_holdout_v1",
        "seed": seed,
        "source_candidate_split": "train",
        "prior_validation_and_test_moved_to_training": True,
        "fresh_validation_and_test_selected_only_from_prior_train": True,
        "previously_evaluated_holdout_patient_count_excluded": len(excluded),
        "patient_disjoint": True,
        "patient_assignment_sha256": assignment_digest,
        "split_patient_counts": dict(sorted(split_counts.items())),
        "target_primary_label_counts": target_counts,
        "output_primary_label_counts": {
            split: dict(
                sorted(
                    Counter(
                        output_labels[patient_id]
                        for patient_id, assigned in output_splits.items()
                        if assigned == split
                    ).items()
                )
            )
            for split in SPLITS
        },
        "limitations": [
            "This is a patient-disjoint engineering holdout, not an independent "
            "clinical validation set.",
            "The split uses published pseudonymous identifiers only inside the "
            "controlled manifest.",
        ],
    }
    return output_rows, provenance


def _write_manifest(path: Path, rows: Sequence[Mapping[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REQUIRED_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--output-manifest", type=Path, required=True)
    parser.add_argument("--provenance", type=Path, required=True)
    parser.add_argument("--seed", required=True)
    parser.add_argument(
        "--exclude-holdout-manifest",
        type=Path,
        action="append",
        default=[],
        help=(
            "Exclude every validation/test patient from an earlier evaluation manifest "
            "when selecting the new holdout. May be repeated."
        ),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    rows, issues = load_manifest(args.source_manifest)
    if issues:
        for issue in issues:
            print(f"Resplit refused [{issue.code}]: {issue.message}", file=sys.stderr)
        return 2
    if args.output_manifest.exists() or args.provenance.exists():
        print("Resplit refused: output paths must not already exist.", file=sys.stderr)
        return 2
    try:
        excluded_patients: set[str] = set()
        exclusion_hashes: list[str] = []
        for exclusion_path in args.exclude_holdout_manifest:
            exclusion_rows, exclusion_issues = load_manifest(exclusion_path)
            if exclusion_issues:
                raise ValueError(f"Cannot read exclusion manifest: {exclusion_path}")
            excluded_patients.update(
                row["patient_id"]
                for row in exclusion_rows
                if row["split"] in {"validation", "test"}
            )
            exclusion_hashes.append(_sha256(exclusion_path))
        output_rows, provenance = create_fresh_holdout(
            rows,
            seed=args.seed,
            excluded_holdout_patient_ids=excluded_patients,
        )
        provenance["source_manifest_sha256"] = _sha256(args.source_manifest)
        provenance["excluded_holdout_manifest_sha256"] = sorted(exclusion_hashes)
        _write_manifest(args.output_manifest, output_rows)
        provenance["output_manifest_sha256"] = _sha256(args.output_manifest)
        args.provenance.parent.mkdir(parents=True, exist_ok=True)
        args.provenance.write_text(
            json.dumps(provenance, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Resplit refused: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(provenance, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())

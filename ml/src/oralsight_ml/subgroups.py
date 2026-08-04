"""Privacy-preserving aggregate subgroup evaluation for held-out prediction metadata."""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .metrics import classification_metrics, multiclass_calibration_metrics


def build_subgroup_report(
    records: Sequence[Mapping[str, Any]],
    *,
    labels: Sequence[str],
    subgroup_fields: Sequence[str],
    minimum_patients: int = 20,
    calibration_bins: int = 10,
) -> dict[str, object]:
    """Aggregate predictions by subgroup and suppress low-patient-count cells."""

    if minimum_patients < 2:
        raise ValueError("minimum_patients must be at least 2.")
    if not records:
        raise ValueError("records must not be empty.")
    if not subgroup_fields:
        raise ValueError("At least one subgroup field is required.")

    fields: dict[str, dict[str, object]] = {}
    for field in subgroup_fields:
        grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
        for record in records:
            if not str(record.get("patient_id", "")).strip():
                raise ValueError("Every record requires a pseudonymous patient_id.")
            if field not in record or not str(record[field]).strip():
                raise ValueError(f"Every record requires subgroup field {field!r}.")
            grouped[str(record[field])].append(record)

        groups: dict[str, object] = {}
        for value, rows in sorted(grouped.items()):
            patient_count = len({str(row["patient_id"]) for row in rows})
            base: dict[str, object] = {
                "patient_count": patient_count,
                "sample_count": len(rows),
                "suppressed": patient_count < minimum_patients,
            }
            if patient_count < minimum_patients:
                base["reason"] = f"Fewer than {minimum_patients} unique patients; metrics withheld."
            else:
                y_true = [str(row["y_true"]) for row in rows]
                y_pred = [str(row["y_pred"]) for row in rows]
                probabilities = [row.get("probabilities") for row in rows]
                if any(not isinstance(value, Mapping) for value in probabilities):
                    raise ValueError("Every record requires a probabilities mapping.")
                base["classification"] = classification_metrics(y_true, y_pred, labels)
                base["calibration"] = multiclass_calibration_metrics(
                    y_true,
                    [dict(value) for value in probabilities if isinstance(value, Mapping)],
                    labels,
                    bins=calibration_bins,
                )
            groups[value] = base
        fields[field] = groups

    return {
        "schema_version": "1.0",
        "minimum_patients_for_reporting": minimum_patients,
        "labels": list(labels),
        "subgroups": fields,
        "limitations": [
            "Subgroup metrics describe only the supplied held-out metadata.",
            (
                "Small groups are suppressed; passing aggregate gates does not "
                "establish clinical validity."
            ),
        ],
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="JSON file containing a top-level records array.")
    parser.add_argument("--labels", nargs="+", required=True)
    parser.add_argument("--field", action="append", dest="fields", required=True)
    parser.add_argument("--minimum-patients", type=int, default=20)
    parser.add_argument("--bins", type=int, default=10)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        payload = json.loads(args.input.read_text(encoding="utf-8"))
        records = payload.get("records") if isinstance(payload, dict) else None
        if not isinstance(records, list):
            raise ValueError("Input must contain a top-level records array.")
        report = build_subgroup_report(
            records,
            labels=args.labels,
            subgroup_fields=args.fields,
            minimum_patients=args.minimum_patients,
            calibration_bins=args.bins,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        print(f"Subgroup report failed: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

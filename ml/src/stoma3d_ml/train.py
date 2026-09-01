"""Audited-data-only baseline training command for Stoma3D research tasks."""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path

from .baselines import run_baseline
from .manifest import load_manifest, validate_manifest

TASKS: tuple[str, ...] = (
    "segmentation",
    "anatomy",
    "appearance",
    "disease",
    "reidentification",
)


def _within(child: Path, parent: Path) -> bool:
    try:
        child.resolve(strict=False).relative_to(parent.resolve(strict=False))
        return True
    except ValueError:
        return False


def _topology_errors(rows: Sequence[Mapping[str, str]], task: str) -> list[str]:
    errors: list[str] = []
    split_counts = Counter(row["split"] for row in rows)
    for split in ("train", "validation", "test"):
        if split_counts[split] == 0:
            errors.append(f"A non-empty {split} split is required.")

    if task in {"anatomy", "appearance", "disease"}:
        field = {
            "anatomy": "anatomy_label",
            "appearance": "appearance_label",
            "disease": "disease_label",
        }[task]
        for split in ("train", "validation"):
            labels = {row[field] for row in rows if row["split"] == split}
            if len(labels) < 2:
                errors.append(f"{task} requires at least two labels in the {split} split.")
    elif task == "reidentification":
        for split in ("train", "validation"):
            groups: dict[str, int] = defaultdict(int)
            for row in rows:
                if row["split"] == split:
                    groups[row["lesion_id"]] += 1
            if len(groups) < 2 or not any(count >= 2 for count in groups.values()):
                errors.append(
                    f"reidentification {split} requires two lesion IDs and one repeated lesion."
                )
    return errors


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", required=True, choices=TASKS)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--data-root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--run-id", default="baseline-local")
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--image-size", type=int, default=224)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--learning-rate", type=float, default=0.001)
    parser.add_argument("--mlflow-tracking-uri")
    parser.add_argument(
        "--acknowledge-audited-data",
        action="store_true",
        help="Required explicit acknowledgement; does not bypass manifest checks.",
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if not args.acknowledge_audited_data:
        print(
            (
                "Training refused: --acknowledge-audited-data is required and "
                "never bypasses audit checks."
            ),
            file=sys.stderr,
        )
        return 2
    if not args.data_root.is_dir():
        print("Training refused: data root does not exist or is not a directory.", file=sys.stderr)
        return 2
    if _within(args.output_dir, args.data_root) or _within(args.data_root, args.output_dir):
        print(
            "Training refused: output directory and controlled data root must not overlap.",
            file=sys.stderr,
        )
        return 2
    if args.epochs < 1 or args.batch_size < 1 or args.image_size < 32:
        print(
            "Training refused: epochs/batch size must be positive and image size >= 32.",
            file=sys.stderr,
        )
        return 2
    if not math.isfinite(args.learning_rate) or args.learning_rate <= 0:
        print("Training refused: learning rate must be positive and finite.", file=sys.stderr)
        return 2

    rows, load_issues = load_manifest(args.manifest)
    if load_issues:
        for issue in load_issues:
            print(f"Training refused [{issue.code}]: {issue.message}", file=sys.stderr)
        return 2
    report = validate_manifest(
        rows,
        require_audited=True,
        require_files=True,
        data_root=args.data_root,
        task=args.task,
    )
    topology_errors = _topology_errors(rows, args.task)
    if not report.valid or topology_errors:
        for issue in report.issues:
            location = f" row {issue.row}" if issue.row is not None else ""
            print(f"Training refused [{issue.code}]{location}: {issue.message}", file=sys.stderr)
        for error in topology_errors:
            print(f"Training refused [split_topology]: {error}", file=sys.stderr)
        return 2

    plan = {
        "task": args.task,
        "run_id": args.run_id,
        "row_count": report.row_count,
        "patient_count": report.patient_count,
        "split_patient_counts": dict(report.split_patient_counts),
        "audited": True,
        "will_copy_source_data": False,
    }
    if args.dry_run:
        print(json.dumps(plan, indent=2, sort_keys=True))
        return 0

    try:
        run = run_baseline(
            args.task,
            rows,
            data_root=args.data_root,
            output_dir=args.output_dir,
            run_id=args.run_id,
            seed=args.seed,
            image_size=args.image_size,
            batch_size=args.batch_size,
            epochs=args.epochs,
            learning_rate=args.learning_rate,
            mlflow_tracking_uri=args.mlflow_tracking_uri,
        )
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"Training failed safely: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(run, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())

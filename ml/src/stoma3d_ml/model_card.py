"""Generate a release-gate-aware Markdown model card from aggregate metadata."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .gates import HEADS, evaluate_release_gates

SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")


def _string_list(metadata: Mapping[str, Any], key: str) -> list[str]:
    value = metadata.get(key)
    if (
        not isinstance(value, list)
        or not value
        or any(not isinstance(item, str) or not item.strip() for item in value)
    ):
        raise ValueError(f"metadata.{key} must be a non-empty list of strings.")
    return [item.strip() for item in value]


def validate_model_metadata(metadata: Mapping[str, Any]) -> dict[str, Any]:
    required_strings = ("model_name", "version", "task", "artifact_sha256", "owner")
    normalized: dict[str, Any] = {}
    for key in required_strings:
        value = metadata.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"metadata.{key} must be a non-empty string.")
        normalized[key] = value.strip()
    if normalized["task"] not in HEADS:
        raise ValueError(f"metadata.task must be one of {', '.join(HEADS)}.")
    if not SHA256_PATTERN.fullmatch(normalized["artifact_sha256"]):
        raise ValueError("metadata.artifact_sha256 must be a lowercase SHA-256 hex digest.")

    normalized["intended_uses"] = _string_list(metadata, "intended_uses")
    normalized["out_of_scope_uses"] = _string_list(metadata, "out_of_scope_uses")
    normalized["limitations"] = _string_list(metadata, "limitations")

    datasets = metadata.get("datasets")
    if not isinstance(datasets, list) or not datasets:
        raise ValueError("metadata.datasets must be a non-empty list.")
    clean_datasets: list[dict[str, str]] = []
    for index, dataset in enumerate(datasets):
        if not isinstance(dataset, Mapping):
            raise ValueError(f"metadata.datasets[{index}] must be an object.")
        clean: dict[str, str] = {}
        for key in ("name", "version", "role", "license_status", "provenance_status"):
            value = dataset.get(key)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"metadata.datasets[{index}].{key} must be a string.")
            clean[key] = value.strip()
        if clean["license_status"] != "approved" or clean["provenance_status"] != "complete":
            raise ValueError(
                "Model cards require approved licenses and complete dataset provenance."
            )
        clean_datasets.append(clean)
    normalized["datasets"] = clean_datasets
    normalized["training_code_version"] = str(metadata.get("training_code_version", "unspecified"))
    normalized["evaluation_date"] = str(metadata.get("evaluation_date", "unspecified"))
    return normalized


def generate_model_card(metadata: Mapping[str, Any], evaluation: Mapping[str, Any]) -> str:
    clean = validate_model_metadata(metadata)
    gate_report = evaluate_release_gates(evaluation)
    identity_pairs = (
        ("artifact_sha256", clean["artifact_sha256"]),
        ("code_revision", clean["training_code_version"]),
        ("evaluated_at", clean["evaluation_date"]),
    )
    for evaluation_key, metadata_value in identity_pairs:
        if gate_report[evaluation_key] != metadata_value:
            raise ValueError(f"metadata identity does not match evaluation.{evaluation_key}.")
    heads = gate_report["heads"]
    assert isinstance(heads, dict)
    decision = heads[clean["task"]]
    enabled = bool(decision["enabled"])
    status = "ENABLED" if enabled else "DISABLED / ABSTAIN"

    lines = [
        f"# Model card: {clean['model_name']}",
        "",
        "> **This result is not a diagnosis.** Gate passage is a competition release",
        "> criterion and does not establish clinical validity or regulatory clearance.",
        "",
        "## Identity and release state",
        "",
        f"- Version: `{clean['version']}`",
        f"- Task: `{clean['task']}`",
        f"- Release status: **{status}**",
        f"- Artifact SHA-256: `{clean['artifact_sha256']}`",
        f"- Training code version: `{clean['training_code_version']}`",
        f"- Evaluation ID: `{gate_report['evaluation_id']}`",
        f"- Evaluation date: `{clean['evaluation_date']}`",
        f"- Dataset manifest SHA-256: `{gate_report['dataset_manifest_sha256']}`",
        f"- Threshold version: `{gate_report['threshold_version']}`",
        f"- Owner: {clean['owner']}",
        "",
        "## Gate decision",
        "",
    ]
    if enabled:
        lines.append("All configured evidence for this head met the fixed release gate.")
    else:
        lines.append("This head must remain hidden or return an abstention because:")
        lines.append("")
        lines.extend(f"- {reason}" for reason in decision["reasons"])
    lines.extend(
        [
            "",
            "Aggregate observed metrics:",
            "",
            "```json",
            json.dumps(decision["observed"], indent=2, sort_keys=True),
            "```",
            "",
            "## Intended uses",
            "",
            *[f"- {item}" for item in clean["intended_uses"]],
            "",
            "## Out-of-scope uses",
            "",
            *[f"- {item}" for item in clean["out_of_scope_uses"]],
            "",
            "## Dataset provenance",
            "",
            "| Dataset | Version | Role | License | Provenance |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for dataset in clean["datasets"]:
        cells = [
            str(dataset[key]).replace("|", "\\|")
            for key in ("name", "version", "role", "license_status", "provenance_status")
        ]
        lines.append("| " + " | ".join(cells) + " |")
    lines.extend(
        [
            "",
            "## Known limitations",
            "",
            *[f"- {item}" for item in clean["limitations"]],
            "",
            "## Required monitoring",
            "",
            "- Re-run patient-disjoint and subgroup evaluation for every model or dataset change.",
            (
                "- Revoke the release flag if provenance, calibration, or any "
                "required metric regresses."
            ),
            "- Never use this output alone to provide care guidance or a diagnosis.",
            "",
        ]
    )
    return "\n".join(lines)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metadata", required=True, type=Path)
    parser.add_argument("--evaluation", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        metadata = json.loads(args.metadata.read_text(encoding="utf-8"))
        evaluation = json.loads(args.evaluation.read_text(encoding="utf-8"))
        if not isinstance(metadata, Mapping) or not isinstance(evaluation, Mapping):
            raise ValueError("Metadata and evaluation inputs must be JSON objects.")
        card = generate_model_card(metadata, evaluation)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(card, encoding="utf-8")
        else:
            print(card, end="")
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        print(f"Model-card generation failed: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

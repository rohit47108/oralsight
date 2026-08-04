"""Select a one-model segmentation weight soup using validation data only.

The source checkpoints must share one architecture, initialization seed, data
split, and training configuration. This command never loads test rows. It
interpolates the two selected state dictionaries, chooses thresholds on the
validation split, and exports one ordinary ONNX model for a later exact frozen
evaluation.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .manifest import load_manifest, resolve_data_path, validate_manifest
from .release_training import (
    _build_segmentation_model,
    _choose_presence_and_mask_thresholds,
    _dependencies,
    _device,
    _export_onnx,
    _load_presence_gated_predictions,
    _safe_output_directory,
    _seed_everything,
    _segmentation_gate_selection_key,
    _segmentation_metrics,
    _segmentation_pair_transform,
    _segmentation_selection_score,
    _sha256,
    _workers,
)

MODEL_SOUP_LOSS_VERSION = "validation_model_soup_v1"
DEFAULT_ALPHAS = (0.25, 0.5, 0.75)


def _load_validation_source(path: Path) -> tuple[Mapping[str, object], Path]:
    try:
        source = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read validation source {path}: {exc}") from exc
    if (
        not isinstance(source, Mapping)
        or source.get("task") != "segmentation"
        or source.get("validation_only") is not True
        or source.get("release_evaluation") is not False
    ):
        raise ValueError(f"{path} is not a completed validation-only segmentation run.")
    configuration = source.get("configuration")
    if not isinstance(configuration, Mapping):
        raise ValueError(f"{path} is missing its configuration.")
    weights = path.parent / "model.pt"
    if not weights.is_file() or _sha256(weights) != source.get("weights_sha256"):
        raise ValueError(f"{path} does not have hash-matched model weights.")
    return source, weights


def _compatible_configuration(
    first: Mapping[str, object],
    second: Mapping[str, object],
) -> Mapping[str, object]:
    first_configuration = first["configuration"]
    second_configuration = second["configuration"]
    assert isinstance(first_configuration, Mapping)
    assert isinstance(second_configuration, Mapping)
    required_equal = (
        "architecture",
        "pretrained_imagenet",
        "image_size",
        "batch_size",
        "epochs",
        "learning_rate",
        "seed",
        "normalization_mean",
        "normalization_std",
        "supplemental_segmentation",
        "training_splits",
    )
    mismatches = [
        key
        for key in required_equal
        if first_configuration.get(key) != second_configuration.get(key)
    ]
    if mismatches:
        raise ValueError("Validation sources are not soup-compatible: " + ", ".join(mismatches))
    architecture = first_configuration.get("architecture")
    if not isinstance(architecture, str) or not architecture.startswith("presence_gated_"):
        raise ValueError("Validation model soup requires presence-gated checkpoints.")
    return first_configuration


def _blend_state(
    torch: Any,
    first: Mapping[str, Any],
    second: Mapping[str, Any],
    *,
    second_weight: float,
) -> dict[str, Any]:
    if first.keys() != second.keys():
        raise ValueError("Validation source state dictionaries do not match.")
    blended: dict[str, Any] = {}
    for key in first:
        first_value = first[key]
        second_value = second[key]
        if first_value.shape != second_value.shape or first_value.dtype != second_value.dtype:
            raise ValueError(f"Validation source tensor mismatch: {key}")
        if torch.is_floating_point(first_value):
            blended[key] = torch.lerp(first_value, second_value, second_weight)
        else:
            selected_value = second_value if second_weight >= 0.5 else first_value
            blended[key] = selected_value.clone()
    return blended


def build_validation_soup(
    rows: Sequence[Mapping[str, str]],
    *,
    data_root: Path,
    output: Path,
    first_run: Path,
    second_run: Path,
    alphas: Sequence[float] = DEFAULT_ALPHAS,
) -> dict[str, object]:
    first_source, first_weights_path = _load_validation_source(first_run)
    second_source, second_weights_path = _load_validation_source(second_run)
    configuration = _compatible_configuration(first_source, second_source)
    clean_alphas = sorted(set(float(alpha) for alpha in alphas))
    if not clean_alphas or any(
        not math.isfinite(alpha) or not 0 < alpha < 1 for alpha in clean_alphas
    ):
        raise ValueError("Every soup alpha must be finite and strictly between 0 and 1.")

    torch, _, torchvision, Image = _dependencies()
    seed = int(configuration["seed"])
    image_size = int(configuration["image_size"])
    batch_size = int(configuration["batch_size"])
    architecture = str(configuration["architecture"])
    _seed_everything(torch, seed)

    class ValidationDataset(torch.utils.data.Dataset):
        def __init__(self) -> None:
            self.cached_pairs: list[tuple[Any, Any]] = []
            for row in rows:
                if row["split"] != "validation":
                    continue
                with (
                    Image.open(resolve_data_path(data_root, row["image_path"])) as image,
                    Image.open(resolve_data_path(data_root, row["mask_path"])) as mask,
                ):
                    resized_image = image.convert("RGB").resize(
                        (image_size, image_size),
                        resample=Image.Resampling.BILINEAR,
                    )
                    resized_mask = mask.convert("L").resize(
                        (image_size, image_size),
                        resample=Image.Resampling.NEAREST,
                    )
                    self.cached_pairs.append((resized_image.copy(), resized_mask.copy()))

        def __len__(self) -> int:
            return len(self.cached_pairs)

        def __getitem__(self, index: int) -> tuple[Any, Any]:
            image, mask = self.cached_pairs[index]
            return _segmentation_pair_transform(
                torch,
                torchvision,
                Image,
                image.copy(),
                mask.copy(),
                image_size=image_size,
                train=False,
            )

    validation_dataset = ValidationDataset()
    if not validation_dataset:
        raise ValueError("The validation split is empty.")
    validation_loader = torch.utils.data.DataLoader(
        validation_dataset,
        batch_size=max(batch_size, 8),
        shuffle=False,
        num_workers=_workers(),
        pin_memory=torch.cuda.is_available(),
    )
    try:
        first_state = torch.load(
            first_weights_path,
            map_location="cpu",
            weights_only=True,
        )
        second_state = torch.load(
            second_weights_path,
            map_location="cpu",
            weights_only=True,
        )
    except TypeError:
        first_state = torch.load(first_weights_path, map_location="cpu")
        second_state = torch.load(second_weights_path, map_location="cpu")

    device = _device(torch)
    history: list[dict[str, float | int]] = []
    best_key = (
        False,
        float("-inf"),
        float("-inf"),
        float("-inf"),
    )
    best_state: dict[str, Any] | None = None
    best_entry: dict[str, float | int] | None = None
    for index, alpha in enumerate(clean_alphas, start=1):
        candidate_state = _blend_state(
            torch,
            first_state,
            second_state,
            second_weight=alpha,
        )
        model = _build_segmentation_model(
            torch,
            torchvision,
            pretrained=False,
            architecture=architecture,
        )
        model.load_state_dict(candidate_state)
        model.to(device)
        probabilities, presence, targets = _load_presence_gated_predictions(
            torch,
            model,
            validation_loader,
            device,
        )
        if presence is None:
            raise ValueError("Validation source model does not expose a presence head.")
        presence_threshold, threshold = _choose_presence_and_mask_thresholds(
            torch,
            probabilities,
            presence,
            targets,
        )
        gated = torch.where(
            (presence >= presence_threshold)[:, :, None, None],
            probabilities,
            torch.zeros_like(probabilities),
        )
        metrics = _segmentation_metrics(
            torch,
            gated,
            targets,
            threshold=threshold,
        )
        entry: dict[str, float | int] = {
            "epoch": index,
            "source_b_weight": alpha,
            "validation_dice": float(metrics["dice"]),
            "validation_positive_dice": float(metrics["positive_dice"]),
            "validation_boundary_f1": float(metrics["boundary_f1"]),
            "validation_positive_boundary_f1": float(metrics["positive_boundary_f1"]),
            "threshold": threshold,
            "presence_threshold": presence_threshold,
        }
        history.append(entry)
        selection_key = _segmentation_gate_selection_key(metrics)
        print(
            f"segmentation soup alpha={alpha:.2f}: "
            f"validation Dice={float(metrics['dice']):.4f}, "
            f"positive Dice={float(metrics['positive_dice']):.4f}, "
            f"boundary F1={float(metrics['boundary_f1']):.4f}, "
            f"positive boundary F1={float(metrics['positive_boundary_f1']):.4f}, "
            f"presence threshold={presence_threshold:.2f}",
            flush=True,
        )
        if selection_key > best_key:
            best_key = selection_key
            best_state = {
                key: value.detach().cpu().clone() for key, value in candidate_state.items()
            }
            best_entry = entry
        del model
    if best_state is None or best_entry is None:
        raise RuntimeError("Validation model soup did not produce a checkpoint.")

    weights_path = output / "model.pt"
    torch.save(best_state, weights_path)
    export_model = _build_segmentation_model(
        torch,
        torchvision,
        pretrained=False,
        architecture=architecture,
    )
    export_model.load_state_dict(best_state)
    export_model.presence_threshold = float(best_entry["presence_threshold"])
    export_model.eval()
    artifact_path = output / "segmentation.onnx"
    _export_onnx(torch, export_model, artifact_path, image_size=image_size)

    selected_metrics = {
        "dice": best_entry["validation_dice"],
        "boundary_f1": best_entry["validation_boundary_f1"],
        "positive_dice": best_entry["validation_positive_dice"],
        "positive_boundary_f1": best_entry["validation_positive_boundary_f1"],
    }
    result = {
        "task": "segmentation",
        "artifact": artifact_path.name,
        "artifact_sha256": _sha256(artifact_path),
        "weights_sha256": _sha256(weights_path),
        "configuration": {
            **dict(configuration),
            "segmentation_loss_version": MODEL_SOUP_LOSS_VERSION,
            "selected_training_epochs": 0,
            "selected_validation_epoch": int(best_entry["epoch"]),
            "validation_selection": {
                "source": "weight_interpolation_on_validation_split",
                "selected_source_b_weight": best_entry["source_b_weight"],
                "selected_segmentation_threshold": best_entry["threshold"],
                "selected_presence_threshold": best_entry["presence_threshold"],
                "source_a_run_sha256": _sha256(first_run),
                "source_b_run_sha256": _sha256(second_run),
            },
            "source_training_loss_versions": [
                first_source["configuration"]["segmentation_loss_version"],
                second_source["configuration"]["segmentation_loss_version"],
            ],
        },
        "validation_best_score": _segmentation_selection_score(selected_metrics),
        "history": history,
        "interface": {
            "input_name": "image",
            "output_name": "logits",
            "output_kind": "binary_mask_logits",
            "segmentation_threshold": best_entry["threshold"],
        },
        "release_evaluation": False,
        "locked_test_evaluation": None,
        "validation_only": True,
        "disclaimer": "This result is not a diagnosis.",
    }
    (output / "run.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return result


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--source-a-run", type=Path, required=True)
    parser.add_argument("--source-b-run", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--alpha", type=float, action="append")
    parser.add_argument("--acknowledge-audited-data", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if not args.acknowledge_audited_data:
        print(
            "Model soup refused: --acknowledge-audited-data is required.",
            file=sys.stderr,
        )
        return 2
    if not args.data_root.is_dir():
        print("Model soup refused: data root does not exist.", file=sys.stderr)
        return 2
    rows, load_issues = load_manifest(args.manifest)
    if load_issues:
        for issue in load_issues:
            print(f"Model soup refused [{issue.code}]: {issue.message}", file=sys.stderr)
        return 2
    report = validate_manifest(
        rows,
        require_audited=True,
        require_files=True,
        data_root=args.data_root,
        task="segmentation",
    )
    if not report.valid:
        for issue in report.issues:
            print(f"Model soup refused [{issue.code}]: {issue.message}", file=sys.stderr)
        return 2
    try:
        output = _safe_output_directory(args.output_dir)
        result = build_validation_soup(
            rows,
            data_root=args.data_root,
            output=output,
            first_run=args.source_a_run,
            second_run=args.source_b_run,
            alphas=args.alpha or DEFAULT_ALPHAS,
        )
    except (RuntimeError, ValueError) as exc:
        print(f"Model soup failed: {exc}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "artifact_sha256": result["artifact_sha256"],
                "locked_test_evaluated": False,
                "task": "segmentation",
                "validation_best_score": result["validation_best_score"],
                "validation_only": True,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

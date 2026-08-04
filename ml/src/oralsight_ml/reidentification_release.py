"""Locked release training for lesion re-identification candidate suggestions.

This module trains one compact image encoder and selects a cosine-similarity
threshold using only the validation split. The locked test split is opened only
after the checkpoint and threshold are fixed. A passing model may suggest that
two observations could match; it never confirms or links observations for a
user.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import shutil
import sys
import tempfile
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from itertools import combinations
from pathlib import Path
from typing import Any

from .constants import RELEASE_THRESHOLDS
from .manifest import load_manifest, resolve_data_path, validate_manifest
from .metrics import wilson_lower_bound

PAIR_MANIFEST_COLUMNS: tuple[str, ...] = (
    "pair_id",
    "split",
    "first_sample_id",
    "second_sample_id",
    "expected_match",
    "pair_kind",
)
PAIR_SPLITS = frozenset({"train", "validation", "test"})
PAIR_KINDS = frozenset({"matched", "hard_negative"})
IMAGE_NET_MEAN = (0.485, 0.456, 0.406)
IMAGE_NET_STD = (0.229, 0.224, 0.225)
EMBEDDING_DIMENSIONS = 128


@dataclass(frozen=True, slots=True)
class PairRecord:
    """One declared pair without patient identifiers or source file paths."""

    pair_id: str
    split: str
    first_sample_id: str
    second_sample_id: str
    expected_match: bool
    pair_kind: str

    def as_dict(self) -> dict[str, str]:
        return {
            "pair_id": self.pair_id,
            "split": self.split,
            "first_sample_id": self.first_sample_id,
            "second_sample_id": self.second_sample_id,
            "expected_match": "true" if self.expected_match else "false",
            "pair_kind": self.pair_kind,
        }


def _sample_index(
    rows: Sequence[Mapping[str, str]],
) -> dict[str, Mapping[str, str]]:
    return {row["sample_id"]: row for row in rows}


def _patient_identity(row: Mapping[str, str]) -> tuple[str, str]:
    return row["source_dataset"], row["patient_id"]


def _lesion_identity(row: Mapping[str, str]) -> tuple[str, str, str]:
    return row["source_dataset"], row["patient_id"], row["lesion_id"]


def _canonical_pair(first_sample_id: str, second_sample_id: str) -> tuple[str, str]:
    return tuple(sorted((first_sample_id, second_sample_id)))


def _parse_expected_match(value: str) -> bool | None:
    normalized = value.strip().lower()
    if normalized in {"true", "1"}:
        return True
    if normalized in {"false", "0"}:
        return False
    return None


def load_pair_manifest(
    path: Path,
    *,
    samples: Sequence[Mapping[str, str]],
) -> list[PairRecord]:
    """Load and strictly validate an explicit patient-disjoint pair CSV.

    Pair rows reference the audited sample manifest by sample ID. The loader
    rejects split mismatches, invalid positive identities, easy negatives from
    different anatomical regions, duplicates, and any patient that leaks across
    pair splits.
    """

    if not path.is_file():
        raise ValueError(f"Pair manifest not found: {path}")
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            fieldnames = tuple(reader.fieldnames or ())
            missing = [column for column in PAIR_MANIFEST_COLUMNS if column not in fieldnames]
            if missing:
                raise ValueError("Pair manifest is missing columns: " + ", ".join(missing))
            raw_rows = [
                {key: (value or "").strip() for key, value in row.items() if key is not None}
                for row in reader
            ]
    except (OSError, UnicodeError, csv.Error) as exc:
        raise ValueError(f"Cannot read pair manifest: {exc}") from exc

    if not raw_rows:
        raise ValueError("Pair manifest is empty.")

    sample_by_id = _sample_index(samples)
    errors: list[str] = []
    records: list[PairRecord] = []
    seen_ids: set[str] = set()
    seen_pairs: set[tuple[str, str, str]] = set()
    patient_splits: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row_number, row in enumerate(raw_rows, start=2):
        pair_id = row["pair_id"]
        split = row["split"]
        first_id = row["first_sample_id"]
        second_id = row["second_sample_id"]
        expected_match = _parse_expected_match(row["expected_match"])
        pair_kind = row["pair_kind"]
        prefix = f"row {row_number}"

        if not pair_id:
            errors.append(f"{prefix}: pair_id is blank")
        elif pair_id in seen_ids:
            errors.append(f"{prefix}: duplicate pair_id {pair_id!r}")
        else:
            seen_ids.add(pair_id)
        if split not in PAIR_SPLITS:
            errors.append(f"{prefix}: split must be train, validation, or test")
        if expected_match is None:
            errors.append(f"{prefix}: expected_match must be true, false, 1, or 0")
        if pair_kind not in PAIR_KINDS:
            errors.append(f"{prefix}: pair_kind must be matched or hard_negative")
        if expected_match is not None and (
            (expected_match and pair_kind != "matched")
            or (not expected_match and pair_kind != "hard_negative")
        ):
            errors.append(f"{prefix}: expected_match and pair_kind disagree")
        if first_id == second_id:
            errors.append(f"{prefix}: a sample cannot be paired with itself")
        first = sample_by_id.get(first_id)
        second = sample_by_id.get(second_id)
        if first is None:
            errors.append(f"{prefix}: first_sample_id is not in the sample manifest")
        if second is None:
            errors.append(f"{prefix}: second_sample_id is not in the sample manifest")
        if first is None or second is None or split not in PAIR_SPLITS:
            continue
        if first["split"] != split or second["split"] != split:
            errors.append(f"{prefix}: both samples must belong to the pair split")
        pair_key = (split, *_canonical_pair(first_id, second_id))
        if pair_key in seen_pairs:
            errors.append(f"{prefix}: duplicate unordered sample pair")
        else:
            seen_pairs.add(pair_key)

        for sample in (first, second):
            patient_splits[_patient_identity(sample)].add(split)
        if expected_match is True and _lesion_identity(first) != _lesion_identity(second):
            errors.append(f"{prefix}: matched samples must be the same patient's lesion")
        if expected_match is False:
            if _lesion_identity(first) == _lesion_identity(second):
                errors.append(f"{prefix}: hard negatives must be different lesions")
            if first["region"] != second["region"]:
                errors.append(f"{prefix}: hard negatives must share an anatomical region")
        if expected_match is not None and pair_kind in PAIR_KINDS:
            records.append(
                PairRecord(
                    pair_id=pair_id,
                    split=split,
                    first_sample_id=first_id,
                    second_sample_id=second_id,
                    expected_match=expected_match,
                    pair_kind=pair_kind,
                )
            )

    for identity, splits in patient_splits.items():
        if len(splits) > 1:
            errors.append(
                "patient split leakage: "
                f"source/patient digest {_identity_digest(identity)} appears in {sorted(splits)}"
            )
    if errors:
        preview = "; ".join(errors[:12])
        suffix = f"; plus {len(errors) - 12} more" if len(errors) > 12 else ""
        raise ValueError(f"Pair manifest is invalid: {preview}{suffix}")
    return records


def _identity_digest(identity: tuple[str, str]) -> str:
    return hashlib.sha256("\x00".join(identity).encode()).hexdigest()[:12]


def _stable_rank(seed: int, *parts: str) -> str:
    payload = "\x00".join((str(seed), *parts)).encode()
    return hashlib.sha256(payload).hexdigest()


def _pair_identifier(
    split: str,
    first_sample_id: str,
    second_sample_id: str,
    pair_kind: str,
) -> str:
    first, second = _canonical_pair(first_sample_id, second_sample_id)
    digest = hashlib.sha256("\x00".join((split, first, second, pair_kind)).encode()).hexdigest()[
        :20
    ]
    return f"pair-{digest}"


def generate_deterministic_pairs(
    samples: Sequence[Mapping[str, str]],
    *,
    seed: int = 2026,
    max_matched_pairs_per_lesion: int = 20,
    hard_negatives_per_match: int = 2,
) -> list[PairRecord]:
    """Generate repeatable positive pairs and region-matched hard negatives.

    Positives are drawn only from the same patient and lesion. Negative
    candidates must be a different lesion from the same split and anatomical
    region. Candidates with the same appearance label and device family are
    ranked first; a seeded digest resolves ties without relying on row order.
    """

    if max_matched_pairs_per_lesion < 1:
        raise ValueError("max_matched_pairs_per_lesion must be positive.")
    if hard_negatives_per_match < 1:
        raise ValueError("hard_negatives_per_match must be positive.")

    result: list[PairRecord] = []
    for split in sorted(PAIR_SPLITS):
        split_rows = sorted(
            (row for row in samples if row["split"] == split),
            key=lambda row: row["sample_id"],
        )
        lesion_groups: dict[tuple[str, str, str], list[Mapping[str, str]]] = defaultdict(list)
        for row in split_rows:
            lesion_groups[_lesion_identity(row)].append(row)

        matched: list[PairRecord] = []
        for lesion_identity in sorted(lesion_groups):
            candidates = list(combinations(lesion_groups[lesion_identity], 2))
            candidates.sort(
                key=lambda pair: _stable_rank(
                    seed,
                    split,
                    pair[0]["sample_id"],
                    pair[1]["sample_id"],
                    "matched",
                )
            )
            for first, second in candidates[:max_matched_pairs_per_lesion]:
                matched.append(
                    PairRecord(
                        pair_id=_pair_identifier(
                            split, first["sample_id"], second["sample_id"], "matched"
                        ),
                        split=split,
                        first_sample_id=first["sample_id"],
                        second_sample_id=second["sample_id"],
                        expected_match=True,
                        pair_kind="matched",
                    )
                )
        matched.sort(key=lambda pair: pair.pair_id)
        result.extend(matched)

        sample_by_id = _sample_index(split_rows)
        used_negatives: set[tuple[str, str]] = set()
        for positive in matched:
            anchors = (positive.first_sample_id, positive.second_sample_id)
            added = 0
            for offset in range(len(split_rows) * 2):
                anchor_id = anchors[offset % len(anchors)]
                anchor = sample_by_id[anchor_id]
                candidates = [
                    row
                    for row in split_rows
                    if row["sample_id"] != anchor_id
                    and row["region"] == anchor["region"]
                    and _lesion_identity(row) != _lesion_identity(anchor)
                    and _canonical_pair(anchor_id, row["sample_id"]) not in used_negatives
                ]
                candidates.sort(
                    key=lambda row: (
                        row.get("appearance_label") != anchor.get("appearance_label"),
                        row.get("device_family") != anchor.get("device_family"),
                        _stable_rank(seed, split, anchor_id, row["sample_id"], "hard_negative"),
                    )
                )
                if not candidates:
                    continue
                other = candidates[0]
                unordered = _canonical_pair(anchor_id, other["sample_id"])
                used_negatives.add(unordered)
                result.append(
                    PairRecord(
                        pair_id=_pair_identifier(split, *unordered, "hard_negative"),
                        split=split,
                        first_sample_id=unordered[0],
                        second_sample_id=unordered[1],
                        expected_match=False,
                        pair_kind="hard_negative",
                    )
                )
                added += 1
                if added >= hard_negatives_per_match:
                    break
    return sorted(result, key=lambda pair: (pair.split, pair.pair_kind, pair.pair_id))


def pair_manifest_sha256(pairs: Sequence[PairRecord]) -> str:
    canonical = json.dumps(
        [pair.as_dict() for pair in pairs],
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(canonical).hexdigest()


def pair_inventory(
    pairs: Sequence[PairRecord],
    *,
    samples: Sequence[Mapping[str, str]],
) -> dict[str, dict[str, int]]:
    sample_by_id = _sample_index(samples)
    inventory: dict[str, dict[str, int]] = {}
    for split in sorted(PAIR_SPLITS):
        selected = [pair for pair in pairs if pair.split == split]
        patient_ids = {
            _patient_identity(sample_by_id[sample_id])
            for pair in selected
            for sample_id in (pair.first_sample_id, pair.second_sample_id)
        }
        inventory[split] = {
            "matched_pairs": sum(pair.expected_match for pair in selected),
            "hard_negative_pairs": sum(not pair.expected_match for pair in selected),
            "patients": len(patient_ids),
        }
    return inventory


def validate_pair_inventory(
    pairs: Sequence[PairRecord],
    *,
    samples: Sequence[Mapping[str, str]],
) -> dict[str, dict[str, int]]:
    inventory = pair_inventory(pairs, samples=samples)
    errors: list[str] = []
    for split in ("train", "validation", "test"):
        counts = inventory[split]
        if counts["matched_pairs"] == 0:
            errors.append(f"{split} requires at least one matched pair")
        if counts["hard_negative_pairs"] == 0:
            errors.append(f"{split} requires at least one hard-negative pair")
    if errors:
        raise ValueError("Pair inventory is invalid: " + "; ".join(errors))
    return inventory


def binary_match_metrics(
    scores: Sequence[float],
    expected: Sequence[bool],
    *,
    threshold: float,
) -> dict[str, float | int]:
    if len(scores) != len(expected) or not scores:
        raise ValueError("scores and expected must have the same non-zero length.")
    if not math.isfinite(threshold):
        raise ValueError("threshold must be finite.")
    if any(not math.isfinite(float(score)) for score in scores):
        raise ValueError("scores must all be finite.")
    predicted = [float(score) >= threshold for score in scores]
    true_positive = sum(
        prediction and truth for prediction, truth in zip(predicted, expected, strict=True)
    )
    false_positive = sum(
        prediction and not truth for prediction, truth in zip(predicted, expected, strict=True)
    )
    true_negative = sum(
        not prediction and not truth for prediction, truth in zip(predicted, expected, strict=True)
    )
    false_negative = sum(
        not prediction and truth for prediction, truth in zip(predicted, expected, strict=True)
    )
    predicted_positive = true_positive + false_positive
    actual_positive = true_positive + false_negative
    precision = true_positive / predicted_positive if predicted_positive else 0.0
    recall = true_positive / actual_positive if actual_positive else 0.0
    lower = wilson_lower_bound(true_positive, predicted_positive) if predicted_positive else 0.0
    return {
        "pair_count": len(scores),
        "true_positive_matches": true_positive,
        "false_positive_matches": false_positive,
        "true_negative_matches": true_negative,
        "false_negative_matches": false_negative,
        "predicted_positive_matches": predicted_positive,
        "precision": precision,
        "recall": recall,
        "precision_lower_95": lower,
        "threshold": float(threshold),
    }


def select_precision_first_threshold(
    scores: Sequence[float],
    expected: Sequence[bool],
    *,
    minimum_precision: float | None = None,
) -> dict[str, float | int | bool]:
    """Freeze a validation threshold under a precision-first constraint.

    Thresholds that satisfy the fixed precision target are considered first.
    Within that set, the Wilson lower bound and recall reward evidence supported
    by more than a single easy pair. If no threshold meets the precision target,
    the safest observed precision is selected and the release gate stays closed.
    """

    target = (
        float(RELEASE_THRESHOLDS["reidentification"]["precision"])
        if minimum_precision is None
        else float(minimum_precision)
    )
    if not 0 <= target <= 1:
        raise ValueError("minimum_precision must be between zero and one.")
    candidates = [
        binary_match_metrics(scores, expected, threshold=threshold)
        for threshold in sorted({float(score) for score in scores}, reverse=True)
    ]
    feasible = [candidate for candidate in candidates if candidate["precision"] >= target]
    if feasible:
        selected = max(
            feasible,
            key=lambda item: (
                item["precision_lower_95"],
                item["recall"],
                item["precision"],
                item["threshold"],
            ),
        )
    else:
        selected = max(
            candidates,
            key=lambda item: (
                item["precision"],
                item["precision_lower_95"],
                item["recall"],
                item["threshold"],
            ),
        )
    return {
        **selected,
        "minimum_precision_target": target,
        "precision_target_met": bool(feasible),
    }


def release_gate_from_locked_test(
    locked_test: Mapping[str, float | int],
    *,
    matched_pairs: int,
    hard_negative_pairs: int,
    held_out_patients: int,
    patient_disjoint: bool,
) -> dict[str, object]:
    """Evaluate the fixed release gate without changing runtime release state."""

    thresholds = RELEASE_THRESHOLDS["reidentification"]
    reasons: list[str] = []
    if not patient_disjoint:
        reasons.append("Held-out patients overlap another split.")
    for label, value, threshold_key in (
        ("Matched pairs", matched_pairs, "minimum_matched_pairs"),
        ("Hard-negative pairs", hard_negative_pairs, "minimum_hard_negative_pairs"),
        ("Held-out patients", held_out_patients, "minimum_patients"),
    ):
        minimum = int(thresholds[threshold_key])
        if value < minimum:
            reasons.append(f"{label} {value} is below the required {minimum}.")
    precision = float(locked_test["precision"])
    lower = float(locked_test["precision_lower_95"])
    true_positive = int(locked_test["true_positive_matches"])
    false_positive = int(locked_test["false_positive_matches"])
    false_negative = int(locked_test["false_negative_matches"])
    true_negative = int(locked_test["true_negative_matches"])
    if true_positive + false_negative != matched_pairs:
        reasons.append("Matched-pair counts are internally inconsistent.")
    if false_positive + true_negative != hard_negative_pairs:
        reasons.append("Hard-negative counts are internally inconsistent.")
    if precision < float(thresholds["precision"]):
        reasons.append("Locked-test precision is below the fixed release threshold.")
    if lower < float(thresholds["precision_lower_95"]):
        reasons.append("The locked-test precision lower 95% bound is too low.")
    return {
        "enabled": not reasons,
        "reasons": reasons,
        "thresholds": dict(thresholds),
        "patient_disjoint": patient_disjoint,
        "user_confirmation_required": True,
        "automatic_linking": False,
        "output_mode": "candidate_suggestion_only",
        "matched_pairs": matched_pairs,
        "hard_negative_pairs": hard_negative_pairs,
        "held_out_patients": held_out_patients,
        "true_positive_matches": true_positive,
        "false_positive_matches": false_positive,
        "precision": precision,
        "recall": float(locked_test["recall"]),
        "precision_lower_95": lower,
    }


def _dependencies() -> tuple[Any, Any, Any]:
    try:
        import torch
        import torchvision
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError(
            'Re-identification release training requires the optional "research" dependencies.'
        ) from exc
    return torch, torchvision, Image


def _seed_everything(torch: Any, seed: int) -> None:
    random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True


def _build_encoder(torch: Any, torchvision: Any) -> Any:
    class Encoder(torch.nn.Module):
        def __init__(self) -> None:
            super().__init__()
            backbone = torchvision.models.mobilenet_v3_small(weights=None)
            self.features = backbone.features
            self.pool = torch.nn.AdaptiveAvgPool2d((1, 1))
            input_features = int(backbone.classifier[0].in_features)
            self.projector = torch.nn.Sequential(
                torch.nn.Linear(input_features, 256),
                torch.nn.Hardswish(),
                torch.nn.Dropout(p=0.15),
                torch.nn.Linear(256, EMBEDDING_DIMENSIONS),
            )

        def forward(self, image: Any) -> Any:
            features = self.features(image)
            pooled = self.pool(features).flatten(1)
            return torch.nn.functional.normalize(self.projector(pooled), dim=1)

    return Encoder()


def _transforms(torchvision: Any, image_size: int) -> tuple[Any, Any]:
    transforms = torchvision.transforms
    training = transforms.Compose(
        [
            transforms.RandomResizedCrop(
                (image_size, image_size), scale=(0.80, 1.0), ratio=(0.90, 1.10)
            ),
            transforms.RandomRotation(7),
            transforms.ColorJitter(brightness=0.12, contrast=0.12, saturation=0.08),
            transforms.ToTensor(),
            transforms.Normalize(IMAGE_NET_MEAN, IMAGE_NET_STD),
        ]
    )
    evaluation = transforms.Compose(
        [
            transforms.Resize((image_size, image_size)),
            transforms.ToTensor(),
            transforms.Normalize(IMAGE_NET_MEAN, IMAGE_NET_STD),
        ]
    )
    return training, evaluation


def _score_pairs(
    torch: Any, model: Any, loader: Any, device: Any
) -> tuple[list[float], list[bool]]:
    model.eval()
    scores: list[float] = []
    expected: list[bool] = []
    with torch.inference_mode():
        for first, second, labels in loader:
            first_embedding = model(first.to(device, non_blocking=True))
            second_embedding = model(second.to(device, non_blocking=True))
            similarity = (first_embedding * second_embedding).sum(dim=1)
            scores.extend(float(value) for value in similarity.detach().cpu().tolist())
            expected.extend(bool(value) for value in labels.tolist())
    if not scores:
        raise RuntimeError("The requested pair split is empty.")
    return scores, expected


def _export_onnx(torch: Any, model: Any, output_path: Path, *, image_size: int) -> None:
    model = model.to("cpu").eval()
    dummy = torch.zeros(1, 3, image_size, image_size, dtype=torch.float32)
    options = {
        "input_names": ["image"],
        "output_names": ["embedding"],
        "dynamic_axes": {"image": {0: "batch"}, "embedding": {0: "batch"}},
        "opset_version": 17,
        "do_constant_folding": True,
    }
    try:
        torch.onnx.export(model, dummy, output_path, dynamo=False, **options)
    except TypeError:
        torch.onnx.export(model, dummy, output_path, **options)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _source_revision() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def _manifest_patient_disjoint(samples: Sequence[Mapping[str, str]]) -> bool:
    patient_splits: dict[tuple[str, str], set[str]] = defaultdict(set)
    for sample in samples:
        patient_splits[_patient_identity(sample)].add(sample["split"])
    return all(len(splits) == 1 for splits in patient_splits.values())


def _run_training(
    samples: Sequence[Mapping[str, str]],
    pairs: Sequence[PairRecord],
    *,
    data_root: Path,
    output: Path,
    image_size: int,
    batch_size: int,
    epochs: int,
    learning_rate: float,
    seed: int,
) -> dict[str, object]:
    torch, torchvision, Image = _dependencies()
    _seed_everything(torch, seed)
    training_transform, evaluation_transform = _transforms(torchvision, image_size)
    sample_by_id = _sample_index(samples)

    class PairDataset(torch.utils.data.Dataset):
        def __init__(self, split: str) -> None:
            self.pairs = [pair for pair in pairs if pair.split == split]
            self.transform = training_transform if split == "train" else evaluation_transform

        def __len__(self) -> int:
            return len(self.pairs)

        def _load(self, sample_id: str) -> Any:
            row = sample_by_id[sample_id]
            with Image.open(resolve_data_path(data_root, row["image_path"])) as image:
                return self.transform(image.convert("RGB"))

        def __getitem__(self, index: int) -> tuple[Any, Any, float]:
            pair = self.pairs[index]
            return (
                self._load(pair.first_sample_id),
                self._load(pair.second_sample_id),
                float(pair.expected_match),
            )

    generator = torch.Generator().manual_seed(seed)
    train_loader = torch.utils.data.DataLoader(
        PairDataset("train"),
        batch_size=batch_size,
        shuffle=True,
        generator=generator,
        num_workers=0,
        pin_memory=torch.cuda.is_available(),
    )
    validation_loader = torch.utils.data.DataLoader(
        PairDataset("validation"),
        batch_size=batch_size,
        shuffle=False,
        num_workers=0,
        pin_memory=torch.cuda.is_available(),
    )
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = _build_encoder(torch, torchvision).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate, weight_decay=0.01)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)
    criterion = torch.nn.BCEWithLogitsLoss()
    best_state: dict[str, Any] | None = None
    best_selection: dict[str, float | int | bool] | None = None
    best_key: tuple[float, float, float, float] | None = None
    history: list[dict[str, float | int]] = []
    for epoch in range(1, epochs + 1):
        model.train()
        train_loss = 0.0
        train_count = 0
        for first, second, labels in train_loader:
            first = first.to(device, non_blocking=True)
            second = second.to(device, non_blocking=True)
            labels = labels.float().to(device, non_blocking=True)
            optimizer.zero_grad(set_to_none=True)
            first_embedding = model(first)
            second_embedding = model(second)
            similarity = (first_embedding * second_embedding).sum(dim=1)
            logits = (similarity - 0.50) * 10.0
            loss = criterion(logits, labels)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=5.0)
            optimizer.step()
            count = int(labels.numel())
            train_loss += float(loss.item()) * count
            train_count += count
        scheduler.step()
        scores, expected = _score_pairs(torch, model, validation_loader, device)
        selection = select_precision_first_threshold(scores, expected)
        history.append(
            {
                "epoch": epoch,
                "train_loss": train_loss / max(train_count, 1),
                "validation_precision": float(selection["precision"]),
                "validation_recall": float(selection["recall"]),
                "validation_precision_lower_95": float(selection["precision_lower_95"]),
            }
        )
        key = (
            float(bool(selection["precision_target_met"])),
            float(selection["precision_lower_95"]),
            float(selection["precision"]),
            float(selection["recall"]),
        )
        if best_key is None or key > best_key:
            best_key = key
            best_selection = selection
            best_state = {
                name: value.detach().cpu().clone() for name, value in model.state_dict().items()
            }
    if best_state is None or best_selection is None:
        raise RuntimeError("Re-identification training did not produce a checkpoint.")

    model.load_state_dict(best_state)
    model.to(device)
    # The locked test dataset and its images are not instantiated until the
    # selected checkpoint and validation threshold have both been frozen.
    test_loader = torch.utils.data.DataLoader(
        PairDataset("test"),
        batch_size=batch_size,
        shuffle=False,
        num_workers=0,
        pin_memory=torch.cuda.is_available(),
    )
    test_scores, test_expected = _score_pairs(torch, model, test_loader, device)
    locked_test = binary_match_metrics(
        test_scores,
        test_expected,
        threshold=float(best_selection["threshold"]),
    )

    weights_path = output / "model.pt"
    torch.save(best_state, weights_path)
    artifact_path = output / "lesion_reidentification.onnx"
    _export_onnx(torch, model, artifact_path, image_size=image_size)
    return {
        "artifact": artifact_path.name,
        "artifact_sha256": _sha256(artifact_path),
        "weights_sha256": _sha256(weights_path),
        "validation_selection": best_selection,
        "locked_test": locked_test,
        "history": history,
        "interface": {
            "input_name": "image",
            "output_name": "embedding",
            "input_shape": [1, 3, image_size, image_size],
            "normalization_mean": list(IMAGE_NET_MEAN),
            "normalization_std": list(IMAGE_NET_STD),
            "embedding_dimensions": EMBEDDING_DIMENSIONS,
            "similarity": "cosine",
            "match_threshold": best_selection["threshold"],
        },
    }


def _within(child: Path, parent: Path) -> bool:
    try:
        child.resolve(strict=False).relative_to(parent.resolve(strict=False))
        return True
    except ValueError:
        return False


def _assert_output_available(output: Path) -> None:
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError(f"Refusing to overwrite non-empty training output: {output}")


def _write_release_evidence(
    output: Path,
    result: Mapping[str, object],
    *,
    manifest: Path,
    samples: Sequence[Mapping[str, str]],
    pairs: Sequence[PairRecord],
    pair_source: str,
    inventory: Mapping[str, Mapping[str, int]],
    configuration: Mapping[str, object],
) -> dict[str, object]:
    locked_test = result["locked_test"]
    assert isinstance(locked_test, Mapping)
    test_inventory = inventory["test"]
    patient_disjoint = _manifest_patient_disjoint(samples)
    release_gate = release_gate_from_locked_test(
        locked_test,
        matched_pairs=int(test_inventory["matched_pairs"]),
        hard_negative_pairs=int(test_inventory["hard_negative_pairs"]),
        held_out_patients=int(test_inventory["patients"]),
        patient_disjoint=patient_disjoint,
    )
    evaluated_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    reidentification = {
        key: release_gate[key]
        for key in (
            "patient_disjoint",
            "user_confirmation_required",
            "matched_pairs",
            "hard_negative_pairs",
            "held_out_patients",
            "true_positive_matches",
            "false_positive_matches",
        )
    }
    evidence: dict[str, object] = {
        "schema_version": "1.0",
        "evaluation_id": f"reidentification-locked-test-{result['artifact_sha256'][:12]}",
        "task": "reidentification",
        "artifact_sha256": result["artifact_sha256"],
        "dataset_manifest_sha256": _sha256(manifest.resolve(strict=True)),
        "pair_manifest_sha256": pair_manifest_sha256(pairs),
        "pair_manifest_source": pair_source,
        "code_revision": _source_revision(),
        "evaluated_at": evaluated_at,
        "source_datasets": sorted({sample["source_dataset"] for sample in samples}),
        "data_root_persisted": False,
        "configuration": dict(configuration),
        "pair_inventory": {split: dict(counts) for split, counts in inventory.items()},
        "validation_selection": result["validation_selection"],
        "locked_test": dict(locked_test),
        "interface": result["interface"],
        "reidentification": reidentification,
        "reidentification_release_gate": release_gate,
        "runtime_release_manifest_changed": False,
        "limitations": [
            "A passing result may suggest a possible match only.",
            "Every proposed match requires explicit user confirmation.",
            "This result is not a diagnosis and does not establish clinical validity.",
        ],
        "disclaimer": "This result is not a diagnosis.",
    }
    (output / "locked-test-evaluation.json").write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    run = {
        "schema_version": "1.0",
        "task": "reidentification",
        "artifact": result["artifact"],
        "artifact_sha256": result["artifact_sha256"],
        "weights_sha256": result["weights_sha256"],
        "configuration": dict(configuration),
        "history": result["history"],
        "validation_selection": result["validation_selection"],
        "locked_test_evaluation": "locked-test-evaluation.json",
        "release_enabled_by_evidence": release_gate["enabled"],
        "runtime_release_manifest_changed": False,
        "disclaimer": "This result is not a diagnosis.",
    }
    (output / "run.json").write_text(
        json.dumps(run, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return evidence


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--pair-manifest", type=Path)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--image-size", type=int, default=224)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--epochs", type=int, default=16)
    parser.add_argument("--learning-rate", type=float, default=0.0003)
    parser.add_argument("--max-matched-pairs-per-lesion", type=int, default=20)
    parser.add_argument("--hard-negatives-per-match", type=int, default=2)
    parser.add_argument("--acknowledge-audited-data", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if not args.acknowledge_audited_data:
        print("Training refused: --acknowledge-audited-data is required.", file=sys.stderr)
        return 2
    if not args.data_root.is_dir():
        print("Training refused: data root is not a directory.", file=sys.stderr)
        return 2
    if _within(args.output_dir, args.data_root) or _within(args.data_root, args.output_dir):
        print(
            "Training refused: output directory and controlled data root must not overlap.",
            file=sys.stderr,
        )
        return 2
    if (
        args.image_size < 32
        or args.batch_size < 1
        or args.epochs < 1
        or not math.isfinite(args.learning_rate)
        or args.learning_rate <= 0
    ):
        print("Training refused: invalid training configuration.", file=sys.stderr)
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
        task="reidentification",
    )
    if not report.valid:
        for issue in report.issues:
            print(f"Training refused [{issue.code}]: {issue.message}", file=sys.stderr)
        return 2
    try:
        if args.pair_manifest is not None:
            pairs = load_pair_manifest(args.pair_manifest, samples=rows)
            pair_source = "explicit_audited_pair_manifest"
        else:
            pairs = generate_deterministic_pairs(
                rows,
                seed=args.seed,
                max_matched_pairs_per_lesion=args.max_matched_pairs_per_lesion,
                hard_negatives_per_match=args.hard_negatives_per_match,
            )
            pair_source = "deterministic_generated_from_audited_manifest"
        inventory = validate_pair_inventory(pairs, samples=rows)
        _assert_output_available(args.output_dir)
    except (OSError, ValueError) as exc:
        print(f"Training refused: {exc}", file=sys.stderr)
        return 2

    summary = {
        "valid": True,
        "patient_disjoint": _manifest_patient_disjoint(rows),
        "pair_manifest_source": pair_source,
        "pair_manifest_sha256": pair_manifest_sha256(pairs),
        "pair_inventory": inventory,
        "user_confirmation_required": True,
        "automatic_linking": False,
    }
    if args.dry_run:
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0

    configuration = {
        "seed": args.seed,
        "image_size": args.image_size,
        "batch_size": args.batch_size,
        "epochs": args.epochs,
        "learning_rate": args.learning_rate,
        "max_matched_pairs_per_lesion": args.max_matched_pairs_per_lesion,
        "hard_negatives_per_match": args.hard_negatives_per_match,
        "encoder": "mobilenet_v3_small_128d",
        "pretrained_weights": False,
        "threshold_selected_on": "validation_only",
        "locked_test_opened_after_selection": True,
    }
    output = args.output_dir.resolve(strict=False)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}-", dir=output.parent))
    try:
        result = _run_training(
            rows,
            pairs,
            data_root=args.data_root,
            output=temporary,
            image_size=args.image_size,
            batch_size=args.batch_size,
            epochs=args.epochs,
            learning_rate=args.learning_rate,
            seed=args.seed,
        )
        evidence = _write_release_evidence(
            temporary,
            result,
            manifest=args.manifest,
            samples=rows,
            pairs=pairs,
            pair_source=pair_source,
            inventory=inventory,
            configuration=configuration,
        )
        if output.exists():
            output.rmdir()
        temporary.replace(output)
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"Training failed safely: {exc}", file=sys.stderr)
        return 2
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    print(json.dumps(evidence, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())

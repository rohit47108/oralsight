"""Small, reproducible PyTorch baselines loaded only after the data audit passes.

These models establish an engineering baseline, not medical validity. They never log
images, masks, patient identifiers, or source paths.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .constants import APPEARANCE_CLASSES, DISEASE_CLASSES, MOUTH_REGIONS
from .manifest import resolve_data_path


def _dependencies() -> tuple[Any, Any, Any]:
    try:
        import torch
        from PIL import Image
        from torchvision import transforms
    except ImportError as exc:
        raise RuntimeError(
            'Training requires the optional "research" dependencies. '
            "Run `uv sync --project ml --extra research` in an approved environment."
        ) from exc
    return torch, Image, transforms


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_output_directory(output_dir: Path) -> Path:
    output = output_dir.resolve(strict=False)
    if output.exists() and any(output.iterdir()):
        raise RuntimeError(f"Refusing to overwrite non-empty training output: {output}")
    output.mkdir(parents=True, exist_ok=True)
    return output


def _log_local_mlflow(
    tracking_uri: str | None,
    *,
    task: str,
    run_id: str,
    params: Mapping[str, object],
    metrics: Mapping[str, float],
) -> None:
    if tracking_uri is None:
        return
    parsed = urlparse(tracking_uri)
    has_credentials = parsed.username is not None or parsed.password is not None
    local_file = parsed.scheme == "file" and parsed.hostname in {None, "", "localhost"}
    loopback_http = parsed.scheme in {"http", "https"} and parsed.hostname in {
        "127.0.0.1",
        "::1",
        "localhost",
    }
    if has_credentials or not (local_file or loopback_http):
        raise RuntimeError("MLflow tracking must use a local file or loopback URI.")
    try:
        import mlflow
    except ImportError as exc:
        raise RuntimeError("MLflow was requested but is not installed.") from exc
    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment("stoma3d-research")
    with mlflow.start_run(run_name=run_id):
        mlflow.log_params({key: str(value) for key, value in params.items()})
        mlflow.log_metrics(dict(metrics))
        mlflow.set_tag("task", task)
        mlflow.set_tag("contains_patient_data", "false")
        # Deliberately do not upload weights or any source-data artifacts.


def run_baseline(
    task: str,
    rows: Sequence[Mapping[str, str]],
    *,
    data_root: Path,
    output_dir: Path,
    run_id: str,
    seed: int,
    image_size: int,
    batch_size: int,
    epochs: int,
    learning_rate: float,
    mlflow_tracking_uri: str | None = None,
) -> dict[str, object]:
    """Train the selected baseline and persist weights plus aggregate run metadata."""

    if task in {"anatomy", "appearance", "disease"}:
        result, state = _run_classification(
            task,
            rows,
            data_root=data_root,
            seed=seed,
            image_size=image_size,
            batch_size=batch_size,
            epochs=epochs,
            learning_rate=learning_rate,
        )
    elif task == "segmentation":
        result, state = _run_segmentation(
            rows,
            data_root=data_root,
            seed=seed,
            image_size=image_size,
            batch_size=batch_size,
            epochs=epochs,
            learning_rate=learning_rate,
        )
    elif task == "reidentification":
        result, state = _run_reidentification(
            rows,
            data_root=data_root,
            seed=seed,
            image_size=image_size,
            batch_size=batch_size,
            epochs=epochs,
            learning_rate=learning_rate,
        )
    else:
        raise ValueError(f"Unsupported baseline task: {task}")

    torch, _, _ = _dependencies()
    output = _safe_output_directory(output_dir)
    weights_path = output / "model.pt"
    torch.save(state, weights_path)
    artifact_sha256 = _sha256(weights_path)
    run = {
        "schema_version": "1.0",
        "run_id": run_id,
        "task": task,
        "research_only": True,
        "release_evaluation": False,
        "artifact_sha256": artifact_sha256,
        "configuration": {
            "seed": seed,
            "image_size": image_size,
            "batch_size": batch_size,
            "epochs": epochs,
            "learning_rate": learning_rate,
        },
        "aggregate_validation_metrics": result,
        "disclaimer": (
            "This result is not a diagnosis. Baseline metrics cannot enable a model head."
        ),
    }
    (output / "run.json").write_text(
        json.dumps(run, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    numeric_metrics = {
        key: float(value)
        for key, value in result.items()
        if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
    }
    _log_local_mlflow(
        mlflow_tracking_uri,
        task=task,
        run_id=run_id,
        params=run["configuration"],
        metrics=numeric_metrics,
    )
    return run


def _seed(torch: Any, seed: int) -> None:
    random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def _device(torch: Any) -> Any:
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def _run_classification(
    task: str,
    rows: Sequence[Mapping[str, str]],
    *,
    data_root: Path,
    seed: int,
    image_size: int,
    batch_size: int,
    epochs: int,
    learning_rate: float,
) -> tuple[dict[str, float | int], Mapping[str, Any]]:
    torch, Image, transforms = _dependencies()
    _seed(torch, seed)
    label_field, labels = {
        "anatomy": ("anatomy_label", MOUTH_REGIONS),
        "appearance": ("appearance_label", APPEARANCE_CLASSES),
        "disease": ("disease_label", DISEASE_CLASSES),
    }[task]
    label_to_index = {label: index for index, label in enumerate(labels)}
    transform = transforms.Compose(
        [transforms.Resize((image_size, image_size)), transforms.ToTensor()]
    )

    class Dataset(torch.utils.data.Dataset):
        def __init__(self, split: str) -> None:
            self.rows = [row for row in rows if row["split"] == split]

        def __len__(self) -> int:
            return len(self.rows)

        def __getitem__(self, index: int) -> tuple[Any, int]:
            row = self.rows[index]
            path = resolve_data_path(data_root, row["image_path"])
            with Image.open(path) as image:
                tensor = transform(image.convert("RGB"))
            return tensor, label_to_index[row[label_field]]

    train_loader = torch.utils.data.DataLoader(
        Dataset("train"), batch_size=batch_size, shuffle=True, num_workers=0
    )
    validation_loader = torch.utils.data.DataLoader(
        Dataset("validation"), batch_size=batch_size, shuffle=False, num_workers=0
    )
    model = torch.nn.Sequential(
        torch.nn.Conv2d(3, 16, 3, padding=1),
        torch.nn.ReLU(),
        torch.nn.MaxPool2d(2),
        torch.nn.Conv2d(16, 32, 3, padding=1),
        torch.nn.ReLU(),
        torch.nn.AdaptiveAvgPool2d((1, 1)),
        torch.nn.Flatten(),
        torch.nn.Linear(32, len(labels)),
    )
    device = _device(torch)
    model.to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
    criterion = torch.nn.CrossEntropyLoss()
    for _ in range(epochs):
        model.train()
        for images, targets in train_loader:
            optimizer.zero_grad(set_to_none=True)
            loss = criterion(model(images.to(device)), targets.to(device))
            loss.backward()
            optimizer.step()

    model.eval()
    total = 0
    correct = 0
    loss_total = 0.0
    with torch.no_grad():
        for images, targets in validation_loader:
            logits = model(images.to(device))
            loss = criterion(logits, targets.to(device))
            batch_count = int(targets.numel())
            total += batch_count
            loss_total += float(loss.item()) * batch_count
            correct += int((logits.argmax(dim=1).cpu() == targets).sum().item())
    metrics = {
        "sample_count": total,
        "accuracy": correct / total if total else 0.0,
        "cross_entropy": loss_total / total if total else 0.0,
    }
    return metrics, model.state_dict()


def _run_segmentation(
    rows: Sequence[Mapping[str, str]],
    *,
    data_root: Path,
    seed: int,
    image_size: int,
    batch_size: int,
    epochs: int,
    learning_rate: float,
) -> tuple[dict[str, float | int], Mapping[str, Any]]:
    torch, Image, transforms = _dependencies()
    _seed(torch, seed)
    image_transform = transforms.Compose(
        [transforms.Resize((image_size, image_size)), transforms.ToTensor()]
    )

    class Dataset(torch.utils.data.Dataset):
        def __init__(self, split: str) -> None:
            self.rows = [row for row in rows if row["split"] == split]

        def __len__(self) -> int:
            return len(self.rows)

        def __getitem__(self, index: int) -> tuple[Any, Any]:
            row = self.rows[index]
            with Image.open(resolve_data_path(data_root, row["image_path"])) as image:
                image_tensor = image_transform(image.convert("RGB"))
            with Image.open(resolve_data_path(data_root, row["mask_path"])) as mask:
                resized = mask.convert("L").resize(
                    (image_size, image_size), resample=Image.Resampling.NEAREST
                )
                mask_tensor = torch.tensor(list(resized.getdata()), dtype=torch.uint8).reshape(
                    image_size, image_size
                )
            return image_tensor, (mask_tensor > 0).long()

    train_loader = torch.utils.data.DataLoader(
        Dataset("train"), batch_size=batch_size, shuffle=True, num_workers=0
    )
    validation_loader = torch.utils.data.DataLoader(
        Dataset("validation"), batch_size=batch_size, shuffle=False, num_workers=0
    )
    model = torch.nn.Sequential(
        torch.nn.Conv2d(3, 16, 3, padding=1),
        torch.nn.ReLU(),
        torch.nn.Conv2d(16, 16, 3, padding=1),
        torch.nn.ReLU(),
        torch.nn.Conv2d(16, 2, 1),
    )
    device = _device(torch)
    model.to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
    criterion = torch.nn.CrossEntropyLoss()
    for _ in range(epochs):
        model.train()
        for images, masks in train_loader:
            optimizer.zero_grad(set_to_none=True)
            loss = criterion(model(images.to(device)), masks.to(device))
            loss.backward()
            optimizer.step()

    model.eval()
    dice_values: list[float] = []
    with torch.no_grad():
        for images, masks in validation_loader:
            predictions = model(images.to(device)).argmax(dim=1).cpu().bool()
            truth = masks.bool()
            for prediction, expected in zip(predictions, truth, strict=True):
                intersection = int((prediction & expected).sum().item())
                denominator = int(prediction.sum().item() + expected.sum().item())
                dice_values.append((2 * intersection / denominator) if denominator else 1.0)
    metrics = {
        "sample_count": len(dice_values),
        "dice": sum(dice_values) / len(dice_values) if dice_values else 0.0,
    }
    return metrics, model.state_dict()


def _pairs_for_split(
    rows: Sequence[Mapping[str, str]], split: str
) -> list[tuple[Mapping[str, str], Mapping[str, str], int]]:
    grouped: dict[str, list[Mapping[str, str]]] = defaultdict(list)
    for row in rows:
        if row["split"] == split:
            grouped[row["lesion_id"]].append(row)
    lesion_ids = sorted(grouped)
    pairs: list[tuple[Mapping[str, str], Mapping[str, str], int]] = []
    for index, lesion_id in enumerate(lesion_ids):
        samples = grouped[lesion_id]
        for sample_index in range(len(samples) - 1):
            pairs.append((samples[sample_index], samples[sample_index + 1], 1))
        if len(lesion_ids) > 1:
            other = grouped[lesion_ids[(index + 1) % len(lesion_ids)]][0]
            pairs.append((samples[0], other, 0))
    return pairs


def _run_reidentification(
    rows: Sequence[Mapping[str, str]],
    *,
    data_root: Path,
    seed: int,
    image_size: int,
    batch_size: int,
    epochs: int,
    learning_rate: float,
) -> tuple[dict[str, float | int], Mapping[str, Any]]:
    torch, Image, transforms = _dependencies()
    _seed(torch, seed)
    transform = transforms.Compose(
        [transforms.Resize((image_size, image_size)), transforms.ToTensor()]
    )

    class PairDataset(torch.utils.data.Dataset):
        def __init__(self, split: str) -> None:
            self.pairs = _pairs_for_split(rows, split)

        def __len__(self) -> int:
            return len(self.pairs)

        def _image(self, row: Mapping[str, str]) -> Any:
            with Image.open(resolve_data_path(data_root, row["image_path"])) as image:
                return transform(image.convert("RGB"))

        def __getitem__(self, index: int) -> tuple[Any, Any, float]:
            first, second, label = self.pairs[index]
            return self._image(first), self._image(second), float(label)

    class Encoder(torch.nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.network = torch.nn.Sequential(
                torch.nn.Conv2d(3, 16, 3, padding=1),
                torch.nn.ReLU(),
                torch.nn.MaxPool2d(2),
                torch.nn.Conv2d(16, 32, 3, padding=1),
                torch.nn.ReLU(),
                torch.nn.AdaptiveAvgPool2d((1, 1)),
                torch.nn.Flatten(),
                torch.nn.Linear(32, 32),
            )

        def forward(self, value: Any) -> Any:
            return torch.nn.functional.normalize(self.network(value), dim=1)

    train_loader = torch.utils.data.DataLoader(
        PairDataset("train"), batch_size=batch_size, shuffle=True, num_workers=0
    )
    validation_loader = torch.utils.data.DataLoader(
        PairDataset("validation"), batch_size=batch_size, shuffle=False, num_workers=0
    )
    model = Encoder()
    device = _device(torch)
    model.to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
    criterion = torch.nn.BCEWithLogitsLoss()
    for _ in range(epochs):
        model.train()
        for first, second, targets in train_loader:
            optimizer.zero_grad(set_to_none=True)
            similarity = (model(first.to(device)) * model(second.to(device))).sum(dim=1) * 5
            loss = criterion(similarity, targets.float().to(device))
            loss.backward()
            optimizer.step()

    model.eval()
    true_positive = 0
    false_positive = 0
    total = 0
    correct = 0
    with torch.no_grad():
        for first, second, targets in validation_loader:
            similarity = (model(first.to(device)) * model(second.to(device))).sum(dim=1) * 5
            predictions = (torch.sigmoid(similarity).cpu() >= 0.5).long()
            expected = targets.long()
            total += int(expected.numel())
            correct += int((predictions == expected).sum().item())
            true_positive += int(((predictions == 1) & (expected == 1)).sum().item())
            false_positive += int(((predictions == 1) & (expected == 0)).sum().item())
    predicted_positive = true_positive + false_positive
    metrics = {
        "pair_count": total,
        "accuracy": correct / total if total else 0.0,
        "precision": true_positive / predicted_positive if predicted_positive else 0.0,
    }
    return metrics, model.state_dict()

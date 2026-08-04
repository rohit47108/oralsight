"""Prepare the public SMART-OM dataset for audited OralSight research runs.

The command keeps source images in a controlled, ignored directory. It verifies the
published Figshare archive, derives patient-disjoint splits, converts VIA lesion
polygons into binary masks, and writes task-specific manifests. It never copies source
images into the repository or a model run.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import sys
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Final

from .manifest import REQUIRED_COLUMNS

SMART_OM_ARCHIVE_BYTES: Final = 1_005_947_172
SMART_OM_ARCHIVE_MD5: Final = "27db67d29be86f4f18ec155b4f0159fe"
SMART_OM_DATASET_ID: Final = "SMART-OM-figshare-31341790-v1"
SMART_OM_LICENSE: Final = "CC BY 4.0"
SMART_OM_DOI: Final = "10.6084/m9.figshare.31341790.v1"

IMAGE_SUFFIXES: Final = frozenset({".jpg", ".jpeg", ".png"})
DISEASE_DIRECTORIES: Final[dict[str, str]] = {
    "01. Normal": "normal",
    "02. Variation from normal": "variation",
    "03. OPMD": "opmd",
    "04. Oral Cancer": "oral_cancer",
}
REGION_DIRECTORIES: Final[dict[str, str]] = {
    "01. Dorsal tongue": "dorsal_tongue",
    "02. Ventral tongue": "ventral_tongue",
    "03. Left buccal mucosa": "left_buccal_mucosa",
    "04. Right buccal mucosa": "right_buccal_mucosa",
    "05. Upper lip": "upper_lip",
    "06. Lower lip": "lower_lip",
    "07. Upper arch": "upper_dental_arch",
    "08. Lower arch": "lower_dental_arch",
}
DISEASE_SEVERITY: Final[dict[str, int]] = {
    "normal": 0,
    "variation": 1,
    "opmd": 2,
    "oral_cancer": 3,
}

_SMITA_PATTERN = re.compile(r"(?i)^(SMITA\d+)(?:-\d+)?[_-]([RW])(?:[_-]|\s)")
_LEGACY_REGION_PATTERN = re.compile(r"(?i)^(\d+)\s*-\s*[A-Z]{2}$")


@dataclass(frozen=True)
class SmartOmSample:
    sample_id: str
    patient_id: str
    disease_label: str
    region: str
    image_path: Path


@dataclass(frozen=True)
class PreparationSummary:
    source_dataset: str
    source_doi: str
    source_license: str
    archive_bytes: int
    archive_md5: str
    image_count: int
    patient_count: int
    split_patient_counts: Mapping[str, int]
    disease_image_counts: Mapping[str, int]
    region_image_counts: Mapping[str, int]
    positive_mask_count: int
    negative_mask_count: int
    unmatched_annotation_count: int
    manifest_rows: Mapping[str, int]
    limitations: tuple[str, ...]


def _hash_file(path: Path, algorithm: str) -> str:
    digest = hashlib.new(algorithm)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_archive(path: Path) -> None:
    """Require the exact public Figshare v1 archive before approving manifests."""

    if not path.is_file():
        raise ValueError(f"SMART-OM archive not found: {path}")
    size = path.stat().st_size
    if size != SMART_OM_ARCHIVE_BYTES:
        raise ValueError(
            f"SMART-OM archive size mismatch: expected {SMART_OM_ARCHIVE_BYTES}, got {size}."
        )
    actual = _hash_file(path, "md5")
    if actual != SMART_OM_ARCHIVE_MD5:
        raise ValueError(
            f"SMART-OM archive MD5 mismatch: expected {SMART_OM_ARCHIVE_MD5}, got {actual}."
        )


def patient_id_from_filename(filename: str) -> str:
    """Derive the published subject key while grouping location/visit variants."""

    stem = Path(filename).stem.strip()
    smita = _SMITA_PATTERN.match(stem)
    if smita:
        return smita.group(1).upper()

    legacy_region = _LEGACY_REGION_PATTERN.match(stem)
    if legacy_region:
        return f"legacy-{legacy_region.group(1)}"

    compact = re.sub(r"[^A-Z0-9]+", "", stem.upper())
    if not compact:
        raise ValueError(f"Unable to derive patient identifier from {filename!r}.")
    return f"legacy-{compact}"


def _relative_to(path: Path, root: Path) -> Path:
    try:
        return path.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"{path} must remain inside data root {root}.") from exc


def _sample_id(relative_image: Path) -> str:
    digest = hashlib.sha256(relative_image.as_posix().encode("utf-8")).hexdigest()[:16]
    return f"smartom-{digest}"


def discover_samples(dataset_root: Path, data_root: Path) -> list[SmartOmSample]:
    """Discover only original, unannotated images from the four class folders."""

    samples: list[SmartOmSample] = []
    for disease_directory, disease_label in DISEASE_DIRECTORIES.items():
        unannotated = dataset_root / disease_directory / "01. Unannotated"
        if not unannotated.is_dir():
            raise ValueError(f"Missing SMART-OM directory: {unannotated}")
        for region_directory, region in REGION_DIRECTORIES.items():
            region_root = unannotated / region_directory
            if not region_root.is_dir():
                continue
            for image_path in sorted(region_root.iterdir()):
                if not image_path.is_file() or image_path.suffix.lower() not in IMAGE_SUFFIXES:
                    continue
                relative_image = _relative_to(image_path, data_root)
                samples.append(
                    SmartOmSample(
                        sample_id=_sample_id(relative_image),
                        patient_id=patient_id_from_filename(image_path.name),
                        disease_label=disease_label,
                        region=region,
                        image_path=relative_image,
                    )
                )
    if not samples:
        raise ValueError("No SMART-OM source images were discovered.")
    return samples


def _stable_patient_order(patient_ids: Iterable[str], seed: int) -> list[str]:
    def key(patient_id: str) -> str:
        return hashlib.sha256(f"{seed}:{patient_id}".encode()).hexdigest()

    return sorted(patient_ids, key=key)


def _split_group(patient_ids: Iterable[str], seed: int) -> dict[str, str]:
    ordered = _stable_patient_order(patient_ids, seed)
    count = len(ordered)
    if count == 1:
        return {ordered[0]: "train"}
    if count == 2:
        return {ordered[0]: "train", ordered[1]: "validation"}

    validation_count = max(1, math.floor(count * 0.15))
    test_count = max(1, math.floor(count * 0.15))
    if validation_count + test_count >= count:
        validation_count = 1
        test_count = 1
    train_count = count - validation_count - test_count
    result: dict[str, str] = {}
    for index, patient_id in enumerate(ordered):
        if index < train_count:
            split = "train"
        elif index < train_count + validation_count:
            split = "validation"
        else:
            split = "test"
        result[patient_id] = split
    return result


def assign_patient_splits(samples: Sequence[SmartOmSample], seed: int) -> dict[str, str]:
    """Stratify by each patient's most severe published class, never by image."""

    patient_labels: dict[str, set[str]] = defaultdict(set)
    for sample in samples:
        patient_labels[sample.patient_id].add(sample.disease_label)

    strata: dict[str, list[str]] = defaultdict(list)
    for patient_id, labels in patient_labels.items():
        primary = max(labels, key=lambda value: DISEASE_SEVERITY[value])
        strata[primary].append(patient_id)

    assignments: dict[str, str] = {}
    for index, label in enumerate(sorted(strata, key=DISEASE_SEVERITY.get)):
        assignments.update(_split_group(strata[label], seed + index))
    if len(assignments) != len(patient_labels):
        raise RuntimeError("Not every discovered patient received exactly one split.")
    return assignments


def _annotation_directories(dataset_root: Path) -> Iterable[tuple[str, Path]]:
    for disease_directory in (
        "02. Variation from normal",
        "03. OPMD",
        "04. Oral Cancer",
    ):
        disease_root = dataset_root / disease_directory
        lesion_roots = [
            path
            for path in disease_root.iterdir()
            if path.is_dir() and "Lesion annotation" in path.name
        ]
        if lesion_roots:
            yield disease_directory, lesion_roots[0]


def load_lesion_polygons(
    dataset_root: Path,
) -> dict[tuple[str, str], tuple[tuple[tuple[int, int], ...], ...]]:
    """Load VIA polygon unions keyed by disease folder and original filename."""

    annotations: dict[tuple[str, str], tuple[tuple[tuple[int, int], ...], ...]] = {}
    for disease_directory, lesion_root in _annotation_directories(dataset_root):
        for json_path in sorted(lesion_root.rglob("*.json")):
            try:
                payload = json.loads(json_path.read_text(encoding="utf-8-sig"))
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                raise ValueError(f"Unreadable VIA annotation {json_path}: {exc}") from exc
            metadata = payload.get("_via_img_metadata", {})
            if not isinstance(metadata, dict):
                raise ValueError(f"Invalid VIA metadata object: {json_path}")
            for value in metadata.values():
                if not isinstance(value, dict):
                    continue
                filename = str(value.get("filename", "")).strip()
                polygons: list[tuple[tuple[int, int], ...]] = []
                for region in value.get("regions", []):
                    shape = region.get("shape_attributes", {})
                    if shape.get("name") != "polygon":
                        continue
                    points_x = shape.get("all_points_x", [])
                    points_y = shape.get("all_points_y", [])
                    if (
                        not isinstance(points_x, list)
                        or not isinstance(points_y, list)
                        or len(points_x) != len(points_y)
                        or len(points_x) < 3
                    ):
                        raise ValueError(f"Invalid polygon in {json_path} for {filename}.")
                    polygons.append(
                        tuple((int(x), int(y)) for x, y in zip(points_x, points_y, strict=True))
                    )
                if filename and polygons:
                    key = (disease_directory, filename.casefold())
                    if key in annotations:
                        raise ValueError(
                            f"Duplicate lesion annotation for {disease_directory}/{filename}."
                        )
                    annotations[key] = tuple(polygons)
    return annotations


def _source_lookup(
    samples: Sequence[SmartOmSample], data_root: Path
) -> dict[tuple[str, str], SmartOmSample]:
    lookup: dict[tuple[str, str], SmartOmSample] = {}
    disease_folder_by_label = {value: key for key, value in DISEASE_DIRECTORIES.items()}
    for sample in samples:
        key = (
            disease_folder_by_label[sample.disease_label],
            (data_root / sample.image_path).name.casefold(),
        )
        if key in lookup:
            raise ValueError(f"Duplicate source filename in SMART-OM class: {key}.")
        lookup[key] = sample
    return lookup


def _select_negative_samples(
    samples: Sequence[SmartOmSample],
    assignments: Mapping[str, str],
    positive_samples: Sequence[SmartOmSample],
    seed: int,
    negative_ratio: float,
) -> list[SmartOmSample]:
    positives_by_split: dict[str, int] = defaultdict(int)
    for sample in positive_samples:
        positives_by_split[assignments[sample.patient_id]] += 1

    normal_by_split: dict[str, list[SmartOmSample]] = defaultdict(list)
    for sample in samples:
        if sample.disease_label == "normal":
            normal_by_split[assignments[sample.patient_id]].append(sample)

    selected: list[SmartOmSample] = []
    for split, candidates in normal_by_split.items():
        limit = min(
            len(candidates),
            max(1, math.ceil(positives_by_split[split] * negative_ratio)),
        )
        ordered = sorted(
            candidates,
            key=lambda sample: hashlib.sha256(f"{seed}:{sample.sample_id}".encode()).hexdigest(),
        )
        selected.extend(ordered[:limit])
    return selected


def _write_mask(
    source_path: Path,
    output_path: Path,
    polygons: Sequence[Sequence[tuple[int, int]]],
) -> None:
    try:
        from PIL import Image, ImageDraw
    except ImportError as exc:
        raise RuntimeError(
            'SMART-OM preparation requires Pillow. Install the "research" extra.'
        ) from exc

    with Image.open(source_path) as image:
        width, height = image.size
    mask = Image.new("L", (width, height), 0)
    if polygons:
        draw = ImageDraw.Draw(mask)
        for polygon in polygons:
            draw.polygon(list(polygon), fill=255)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    mask.save(output_path, format="PNG", optimize=True)


def _manifest_row(
    sample: SmartOmSample,
    assignments: Mapping[str, str],
    *,
    mask_path: Path | None = None,
) -> dict[str, str]:
    return {
        "sample_id": sample.sample_id,
        "patient_id": sample.patient_id,
        "split": assignments[sample.patient_id],
        "region": sample.region,
        "image_path": sample.image_path.as_posix(),
        "mask_path": mask_path.as_posix() if mask_path is not None else "",
        "lesion_id": "",
        "anatomy_label": sample.region,
        "appearance_label": "",
        "disease_label": sample.disease_label,
        "device_family": "mixed-ios-android-smartphone",
        "source_dataset": SMART_OM_DATASET_ID,
        "license_status": "approved",
        "audit_status": "approved",
        "consent_scope": "research_training",
    }


def _write_manifest(path: Path, rows: Sequence[Mapping[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REQUIRED_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def prepare_smart_om(
    *,
    archive: Path,
    dataset_root: Path,
    data_root: Path,
    output_dir: Path,
    seed: int = 2026,
    negative_ratio: float = 1.0,
) -> PreparationSummary:
    """Verify, prepare masks, and emit audited task manifests."""

    verify_archive(archive)
    if not dataset_root.is_dir():
        raise ValueError(f"Extracted SMART-OM directory not found: {dataset_root}")
    _relative_to(dataset_root, data_root)
    _relative_to(output_dir, data_root)
    if not math.isfinite(negative_ratio) or negative_ratio <= 0:
        raise ValueError("negative_ratio must be positive and finite.")

    samples = discover_samples(dataset_root, data_root)
    assignments = assign_patient_splits(samples, seed)
    annotations = load_lesion_polygons(dataset_root)
    lookup = _source_lookup(samples, data_root)

    annotated: list[tuple[SmartOmSample, Sequence[Sequence[tuple[int, int]]]]] = []
    unmatched = 0
    for key, polygons in annotations.items():
        sample = lookup.get(key)
        if sample is None:
            unmatched += 1
            continue
        annotated.append((sample, polygons))
    positive_samples = [sample for sample, _ in annotated]
    negatives = _select_negative_samples(
        samples,
        assignments,
        positive_samples,
        seed,
        negative_ratio,
    )

    masks_root = output_dir / "masks"
    segmentation_rows: list[dict[str, str]] = []
    for sample, polygons in annotated:
        mask_absolute = masks_root / f"{sample.sample_id}.png"
        _write_mask(data_root / sample.image_path, mask_absolute, polygons)
        segmentation_rows.append(
            _manifest_row(
                sample,
                assignments,
                mask_path=_relative_to(mask_absolute, data_root),
            )
        )
    for sample in negatives:
        mask_absolute = masks_root / f"{sample.sample_id}.png"
        _write_mask(data_root / sample.image_path, mask_absolute, ())
        segmentation_rows.append(
            _manifest_row(
                sample,
                assignments,
                mask_path=_relative_to(mask_absolute, data_root),
            )
        )

    ordered = sorted(samples, key=lambda sample: (assignments[sample.patient_id], sample.sample_id))
    segmentation_rows.sort(key=lambda row: (row["split"], row["sample_id"]))
    anatomy_rows = [_manifest_row(sample, assignments) for sample in ordered]
    disease_rows = [_manifest_row(sample, assignments) for sample in ordered]

    manifests_root = output_dir / "manifests"
    _write_manifest(manifests_root / "smart-om-anatomy.csv", anatomy_rows)
    _write_manifest(manifests_root / "smart-om-disease.csv", disease_rows)
    _write_manifest(manifests_root / "smart-om-segmentation.csv", segmentation_rows)

    split_patients: dict[str, set[str]] = defaultdict(set)
    disease_counts: dict[str, int] = defaultdict(int)
    region_counts: dict[str, int] = defaultdict(int)
    for sample in samples:
        split_patients[assignments[sample.patient_id]].add(sample.patient_id)
        disease_counts[sample.disease_label] += 1
        region_counts[sample.region] += 1

    summary = PreparationSummary(
        source_dataset=SMART_OM_DATASET_ID,
        source_doi=SMART_OM_DOI,
        source_license=SMART_OM_LICENSE,
        archive_bytes=archive.stat().st_size,
        archive_md5=SMART_OM_ARCHIVE_MD5,
        image_count=len(samples),
        patient_count=len(assignments),
        split_patient_counts={
            split: len(patients) for split, patients in sorted(split_patients.items())
        },
        disease_image_counts=dict(sorted(disease_counts.items())),
        region_image_counts=dict(sorted(region_counts.items())),
        positive_mask_count=len(annotated),
        negative_mask_count=len(negatives),
        unmatched_annotation_count=unmatched,
        manifest_rows={
            "anatomy": len(anatomy_rows),
            "disease": len(disease_rows),
            "segmentation": len(segmentation_rows),
        },
        limitations=(
            "SMART-OM is cross-sectional and cannot release lesion re-identification.",
            "SMART-OM has no canonical seven-class appearance labels.",
            "The oral-cancer class cannot satisfy the independent 100-patient release gate.",
            "Published filenames yield fewer stable subject keys than the paper's "
            "reported enrollment; all filename variants are conservatively grouped.",
        ),
    )
    (output_dir / "audit-summary.json").write_text(
        json.dumps(asdict(summary), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--dataset-root", required=True, type=Path)
    parser.add_argument("--data-root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--negative-ratio", type=float, default=1.0)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        summary = prepare_smart_om(
            archive=args.archive,
            dataset_root=args.dataset_root,
            data_root=args.data_root,
            output_dir=args.output_dir,
            seed=args.seed,
            negative_ratio=args.negative_ratio,
        )
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"SMART-OM preparation failed safely: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(asdict(summary), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())

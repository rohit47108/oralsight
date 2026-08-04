from __future__ import annotations

import hashlib
import json
from pathlib import Path

from oralsight_ml.smart_om import (
    SmartOmSample,
    assign_patient_splits,
    discover_samples,
    load_lesion_polygons,
    patient_id_from_filename,
)


def test_patient_id_groups_capture_location_and_visit_variants() -> None:
    assert patient_id_from_filename("SMITA00024-1_R_DT.JPG") == "SMITA00024"
    assert patient_id_from_filename("SMITA00024_W_VT.jpeg") == "SMITA00024"
    assert patient_id_from_filename("5 - DT.jpg") == "legacy-5"
    assert patient_id_from_filename("6026.jpg") == "legacy-6026"
    assert patient_id_from_filename("Ca 1.JPG") == "legacy-CA1"


def test_patient_split_is_deterministic_and_disjoint() -> None:
    samples = [
        SmartOmSample(
            sample_id=f"sample-{patient}-{index}",
            patient_id=patient,
            disease_label=label,
            region="dorsal_tongue",
            image_path=Path(f"{patient}-{index}.jpg"),
        )
        for index, (patient, label) in enumerate(
            [
                ("p1", "normal"),
                ("p1", "variation"),
                ("p2", "normal"),
                ("p3", "normal"),
                ("p4", "variation"),
                ("p5", "variation"),
                ("p6", "opmd"),
                ("p7", "opmd"),
                ("p8", "opmd"),
                ("p9", "oral_cancer"),
                ("p10", "oral_cancer"),
                ("p11", "oral_cancer"),
            ]
        )
    ]

    first = assign_patient_splits(samples, 2026)
    second = assign_patient_splits(list(reversed(samples)), 2026)

    assert first == second
    assert set(first) == {sample.patient_id for sample in samples}
    assert first["p1"] in {"train", "validation", "test"}


def test_discovers_original_images_and_reads_via_polygons(tmp_path: Path) -> None:
    data_root = tmp_path / "controlled"
    dataset_root = data_root / "SMART-OM"
    for disease in (
        "01. Normal",
        "02. Variation from normal",
        "03. OPMD",
        "04. Oral Cancer",
    ):
        for region in (
            "01. Dorsal tongue",
            "02. Ventral tongue",
            "03. Left buccal mucosa",
            "04. Right buccal mucosa",
            "05. Upper lip",
            "06. Lower lip",
            "07. Upper arch",
            "08. Lower arch",
        ):
            (dataset_root / disease / "01. Unannotated" / region).mkdir(parents=True, exist_ok=True)

    image_path = (
        dataset_root / "03. OPMD" / "01. Unannotated" / "02. Ventral tongue" / "SMITA00001_R_VT.jpg"
    )
    image_path.write_bytes(b"source-image-placeholder")

    lesion_json = (
        dataset_root
        / "03. OPMD"
        / "04. Lesion annotation"
        / "Lesion Json"
        / "SMITA00001_R_lesion.json"
    )
    lesion_json.parent.mkdir(parents=True)
    payload = {
        "_via_img_metadata": {
            "key": {
                "filename": image_path.name,
                "regions": [
                    {
                        "shape_attributes": {
                            "name": "polygon",
                            "all_points_x": [1, 10, 5],
                            "all_points_y": [1, 1, 8],
                        }
                    }
                ],
            }
        }
    }
    lesion_json.write_text(json.dumps(payload), encoding="utf-8")

    samples = discover_samples(dataset_root, data_root)
    polygons = load_lesion_polygons(dataset_root)

    assert len(samples) == 1
    assert samples[0].patient_id == "SMITA00001"
    assert samples[0].region == "ventral_tongue"
    assert samples[0].sample_id == (
        "smartom-" + hashlib.sha256(samples[0].image_path.as_posix().encode()).hexdigest()[:16]
    )
    assert polygons[("03. OPMD", image_path.name.casefold())] == (((1, 1), (10, 1), (5, 8)),)

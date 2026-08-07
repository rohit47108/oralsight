from __future__ import annotations

import hashlib
import json
import struct
from io import BytesIO
from uuid import UUID

from PIL import Image, ImageDraw

from oralsight_worker.local_artifacts import (
    LocalArtifact,
    SourceView,
    SurfaceAbstention,
    build_observation_surface,
)
from oralsight_worker.models import AssetPointer, ReconstructionView


def source_image() -> bytes:
    image = Image.new("RGB", (160, 160), "#F3D0C9")
    draw = ImageDraw.Draw(image)
    for offset in range(0, 160, 10):
        draw.line((0, offset, 159, 159 - offset), fill="#712D3A", width=3)
        draw.line((offset, 0, 159 - offset, 159), fill="#FFF8F2", width=2)
    output = BytesIO()
    image.save(output, format="JPEG", quality=94)
    return output.getvalue()


def sources(angles=("center", "left", "right")) -> list[SourceView]:
    data = source_image()
    pointer = AssetPointer(
        asset_id=UUID("10000000-0000-4000-8000-000000000001"),
        sha256=hashlib.sha256(data).hexdigest(),
        media_type="image/jpeg",
        size_bytes=len(data),
    )
    return [
        SourceView(
            view=ReconstructionView(
                capture_id=UUID(f"20000000-0000-4000-8000-{index:012d}"),
                image=pointer,
                region="dorsal_tongue",
                angle_label=angle,
            ),
            data=data,
        )
        for index, angle in enumerate(angles, start=1)
    ]


def glb_json(data: bytes) -> dict:
    magic, version, total_length = struct.unpack_from("<4sII", data, 0)
    assert magic == b"glTF"
    assert version == 2
    assert total_length == len(data)
    json_length, chunk_type = struct.unpack_from("<I4s", data, 12)
    assert chunk_type == b"JSON"
    return json.loads(data[20 : 20 + json_length])


def test_surface_is_deterministic_valid_glb_with_embedded_provenance() -> None:
    arguments = {
        "capture_set_id": "30000000-0000-4000-8000-000000000001",
        "calibration_id": "40000000-0000-4000-8000-000000000001",
        "generated_at": "2026-08-04T12:00:00Z",
    }
    first = build_observation_surface(sources(), **arguments)
    second = build_observation_surface(sources(), **arguments)

    assert isinstance(first, LocalArtifact)
    assert isinstance(second, LocalArtifact)
    assert first.data == second.data
    assert first.sha256 == hashlib.sha256(first.data).hexdigest()
    document = glb_json(first.data)
    extras = document["asset"]["extras"]
    assert extras["status"] == "complete"
    assert extras["notAnatomicalDigitalTwin"] is True
    assert extras["calibrationEvidence"]["status"] == "reference_received_unverified"
    assert extras["calibrationEvidence"]["physicalScaleUsed"] is False
    assert len(document["nodes"]) == 8
    assert {node["extras"]["regionId"] for node in document["nodes"]} == {
        "dorsal_tongue",
        "ventral_tongue",
        "left_buccal_mucosa",
        "right_buccal_mucosa",
        "upper_lip",
        "lower_lip",
        "upper_dental_arch",
        "lower_dental_arch",
    }


def test_surface_abstains_without_three_unique_usable_angles() -> None:
    result = build_observation_surface(
        sources(("center", "center", "center")),
        capture_set_id="30000000-0000-4000-8000-000000000001",
        calibration_id=None,
        generated_at="2026-08-04T12:00:00Z",
    )

    assert isinstance(result, SurfaceAbstention)
    assert result.reason_code == "insufficient_reconstruction_angle_coverage"
    assert result.manifest["status"] == "abstained"
    assert result.manifest["abstentionReasons"] == ["fewer_than_three_unique_angles"]

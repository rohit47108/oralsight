"""Deterministic local observation-surface and summary-video renderers."""

from __future__ import annotations

import hashlib
import json
import math
import struct
import subprocess
import textwrap
from collections import defaultdict
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from uuid import UUID

import cv2
import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps, UnidentifiedImageError

from .models import (
    MouthRegion,
    ReconstructionView,
    SummaryVideoObservation,
    SummaryVideoPayload,
    VideoCandidateMask,
)

DISCLAIMER = "This result is not a diagnosis."
SURFACE_ALGORITHM_VERSION = "oralsight-observation-surface/1.0.0"
VIDEO_RENDERER_VERSION = "oralsight-summary-video/2.0.0"
MAX_IMAGE_PIXELS = 20_000_000
Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS


@dataclass(frozen=True, slots=True)
class SourceView:
    view: ReconstructionView
    data: bytes


@dataclass(frozen=True, slots=True)
class LocalArtifact:
    data: bytes
    filename: str
    media_type: str
    sha256: str
    manifest: dict[str, Any]


@dataclass(frozen=True, slots=True)
class SurfaceAbstention:
    reason_code: str
    manifest: dict[str, Any]


REGION_LAYOUT: dict[MouthRegion, dict[str, Any]] = {
    MouthRegion.DORSAL_TONGUE: {
        "mesh": "tongue_dorsal",
        "translation": [0.0, -0.36, 0.28],
        "scale": [1.15, 0.72, 0.42],
    },
    MouthRegion.VENTRAL_TONGUE: {
        "mesh": "tongue_ventral",
        "translation": [0.0, -0.72, -0.02],
        "scale": [0.72, 0.26, 0.3],
    },
    MouthRegion.LEFT_BUCCAL_MUCOSA: {
        "mesh": "buccal_left",
        "translation": [-1.02, 0.0, 0.0],
        "scale": [0.42, 1.26, 0.6],
    },
    MouthRegion.RIGHT_BUCCAL_MUCOSA: {
        "mesh": "buccal_right",
        "translation": [1.02, 0.0, 0.0],
        "scale": [0.42, 1.26, 0.6],
    },
    MouthRegion.UPPER_LIP: {
        "mesh": "lip_upper",
        "translation": [0.0, 0.82, 0.34],
        "scale": [1.48, 0.26, 0.35],
    },
    MouthRegion.LOWER_LIP: {
        "mesh": "lip_lower",
        "translation": [0.0, -1.03, 0.32],
        "scale": [1.35, 0.26, 0.35],
    },
    MouthRegion.UPPER_DENTAL_ARCH: {
        "mesh": "arch_upper",
        "translation": [0.0, 0.45, -0.02],
        "scale": [1.1, 0.26, 0.25],
    },
    MouthRegion.LOWER_DENTAL_ARCH: {
        "mesh": "arch_lower",
        "translation": [0.0, -0.52, -0.2],
        "scale": [1.08, 0.24, 0.25],
    },
}


def _round(value: float) -> float:
    return round(float(value), 6)


def inspect_source_view(source: SourceView) -> dict[str, Any]:
    evidence: dict[str, Any] = {
        "captureId": str(source.view.capture_id),
        "assetId": str(source.view.image.asset_id),
        "sourceSha256": source.view.image.sha256,
        "region": source.view.region.value,
        "angleLabel": source.view.angle_label,
        "cameraPoseId": (
            str(source.view.camera_pose_id) if source.view.camera_pose_id else None
        ),
        "accepted": False,
        "reasons": [],
    }
    try:
        with Image.open(BytesIO(source.data)) as probe:
            width, height = probe.size
            if width * height > MAX_IMAGE_PIXELS:
                evidence["reasons"] = ["image_dimensions_exceed_limit"]
                return evidence
            probe.verify()
        with Image.open(BytesIO(source.data)) as decoded:
            image = decoded.convert("RGB")
            width, height = image.size
            image.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
            rgb = np.asarray(image, dtype=np.uint8)
    except (Image.DecompressionBombError, UnidentifiedImageError, OSError, ValueError):
        evidence["reasons"] = ["image_decode_failed"]
        return evidence

    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    luminance = float(np.mean(gray))
    contrast = float(np.std(gray))
    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    exposure_score = max(0.0, 1.0 - abs(luminance - 127.5) / 127.5)
    contrast_score = min(1.0, contrast / 48.0)
    sharpness_score = min(1.0, sharpness / 100.0)
    reasons: list[str] = []
    if min(width, height) < 64:
        reasons.append("image_resolution_too_low")
    if exposure_score < 0.25:
        reasons.append("image_exposure_out_of_range")
    if contrast_score < 0.05:
        reasons.append("image_contrast_too_low")
    if sharpness_score < 0.08:
        reasons.append("image_blur_too_high")

    mean_rgb = np.mean(rgb.reshape(-1, 3), axis=0)
    evidence.update(
        {
            "width": width,
            "height": height,
            "exposureScore": _round(exposure_score),
            "contrastScore": _round(contrast_score),
            "sharpnessScore": _round(sharpness_score),
            "meanRgb": [_round(channel / 255.0) for channel in mean_rgb],
            "accepted": not reasons,
            "reasons": reasons,
        }
    )
    return evidence


def _sphere_geometry(
    latitude_segments: int = 10, longitude_segments: int = 16
) -> tuple[bytes, bytes, bytes, int, int]:
    positions: list[float] = []
    normals: list[float] = []
    indices: list[int] = []
    for latitude in range(latitude_segments + 1):
        theta = math.pi * latitude / latitude_segments
        sin_theta = math.sin(theta)
        cos_theta = math.cos(theta)
        for longitude in range(longitude_segments + 1):
            phi = 2 * math.pi * longitude / longitude_segments
            x = sin_theta * math.cos(phi)
            y = cos_theta
            z = sin_theta * math.sin(phi)
            positions.extend((x * 0.55, y * 0.55, z * 0.55))
            normals.extend((x, y, z))
    row = longitude_segments + 1
    for latitude in range(latitude_segments):
        for longitude in range(longitude_segments):
            first = latitude * row + longitude
            second = first + row
            indices.extend((first, second, first + 1, second, second + 1, first + 1))
    return (
        struct.pack(f"<{len(positions)}f", *positions),
        struct.pack(f"<{len(normals)}f", *normals),
        struct.pack(f"<{len(indices)}H", *indices),
        len(positions) // 3,
        len(indices),
    )


def _pad4(value: bytes, pad: bytes = b"\x00") -> bytes:
    return value + pad * ((-len(value)) % 4)


def _build_glb(manifest: dict[str, Any]) -> bytes:
    position_bytes, normal_bytes, index_bytes, vertex_count, index_count = (
        _sphere_geometry()
    )
    position_offset = 0
    normal_offset = len(position_bytes)
    index_offset = normal_offset + len(normal_bytes)
    binary = _pad4(position_bytes + normal_bytes + index_bytes)

    region_evidence = {item["region"]: item for item in manifest["regions"]}
    materials: list[dict[str, Any]] = []
    meshes: list[dict[str, Any]] = []
    nodes: list[dict[str, Any]] = []
    for region, layout in REGION_LAYOUT.items():
        evidence = region_evidence[region.value]
        mean_rgb = evidence["meanRgb"]
        if evidence["acceptedViewCount"]:
            base = [0.72, 0.34, 0.38]
            color = [
                _round(base[index] * 0.72 + mean_rgb[index] * 0.28)
                for index in range(3)
            ]
        else:
            color = [0.51, 0.62, 0.64]
        material_index = len(materials)
        materials.append(
            {
                "name": f"coverage_{region.value}",
                "pbrMetallicRoughness": {
                    "baseColorFactor": [*color, 1.0],
                    "metallicFactor": 0.0,
                    "roughnessFactor": 0.78,
                },
                "extras": {
                    "derivedFromImageColor": bool(evidence["acceptedViewCount"]),
                    "notDiagnosticColor": True,
                },
            }
        )
        mesh_index = len(meshes)
        meshes.append(
            {
                "name": layout["mesh"],
                "primitives": [
                    {
                        "attributes": {"POSITION": 0, "NORMAL": 1},
                        "indices": 2,
                        "material": material_index,
                    }
                ],
            }
        )
        nodes.append(
            {
                "name": layout["mesh"],
                "mesh": mesh_index,
                "translation": layout["translation"],
                "scale": layout["scale"],
                "extras": {
                    "regionId": region.value,
                    "coverage": evidence["coverage"],
                    "acceptedViewCount": evidence["acceptedViewCount"],
                    "captureIds": evidence["captureIds"],
                    "angleLabels": evidence["angleLabels"],
                },
            }
        )

    gltf = {
        "asset": {
            "version": "2.0",
            "generator": SURFACE_ALGORITHM_VERSION,
            "extras": manifest,
        },
        "scene": 0,
        "scenes": [{"name": "Oral observation surface", "nodes": list(range(8))}],
        "nodes": nodes,
        "meshes": meshes,
        "materials": materials,
        "buffers": [{"byteLength": len(binary)}],
        "bufferViews": [
            {
                "buffer": 0,
                "byteOffset": position_offset,
                "byteLength": len(position_bytes),
                "target": 34962,
            },
            {
                "buffer": 0,
                "byteOffset": normal_offset,
                "byteLength": len(normal_bytes),
                "target": 34962,
            },
            {
                "buffer": 0,
                "byteOffset": index_offset,
                "byteLength": len(index_bytes),
                "target": 34963,
            },
        ],
        "accessors": [
            {
                "bufferView": 0,
                "componentType": 5126,
                "count": vertex_count,
                "type": "VEC3",
                "min": [-0.55, -0.55, -0.55],
                "max": [0.55, 0.55, 0.55],
            },
            {
                "bufferView": 1,
                "componentType": 5126,
                "count": vertex_count,
                "type": "VEC3",
            },
            {
                "bufferView": 2,
                "componentType": 5123,
                "count": index_count,
                "type": "SCALAR",
                "min": [0],
                "max": [vertex_count - 1],
            },
        ],
    }
    json_chunk = _pad4(
        json.dumps(gltf, sort_keys=True, separators=(",", ":")).encode(), b" "
    )
    total_length = 12 + 8 + len(json_chunk) + 8 + len(binary)
    return b"".join(
        (
            struct.pack("<4sII", b"glTF", 2, total_length),
            struct.pack("<I4s", len(json_chunk), b"JSON"),
            json_chunk,
            struct.pack("<I4s", len(binary), b"BIN\x00"),
            binary,
        )
    )


def build_observation_surface_from_evidence(
    views: list[dict[str, Any]],
    *,
    capture_set_id: str,
    calibration_id: str | None,
    generated_at: str,
) -> LocalArtifact | SurfaceAbstention:
    accepted = [view for view in views if view["accepted"]]
    unique_angles = {view["angleLabel"] for view in accepted}
    regions: list[dict[str, Any]] = []
    grouped: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for view in accepted:
        grouped[view["region"]].append(view)
    for region in MouthRegion:
        region_views = grouped[region.value]
        mean_rgb = (
            [
                _round(
                    sum(view["meanRgb"][index] for view in region_views)
                    / len(region_views)
                )
                for index in range(3)
            ]
            if region_views
            else [0.0, 0.0, 0.0]
        )
        regions.append(
            {
                "region": region.value,
                "meshName": REGION_LAYOUT[region]["mesh"],
                "coverage": "observed" if region_views else "not_observed",
                "acceptedViewCount": len(region_views),
                "captureIds": [view["captureId"] for view in region_views],
                "angleLabels": sorted({view["angleLabel"] for view in region_views}),
                "meanRgb": mean_rgb,
            }
        )
    quality_score = (
        _round(
            sum(
                min(
                    view["exposureScore"],
                    view["contrastScore"],
                    view["sharpnessScore"],
                )
                for view in accepted
            )
            / len(accepted)
        )
        if accepted
        else 0.0
    )
    manifest: dict[str, Any] = {
        "schemaVersion": "oralsight.observation-surface.v1",
        "label": "personalized oral observation surface",
        "approximationLabel": "oral observation surface",
        "notAnatomicalDigitalTwin": True,
        "notForDiagnosis": True,
        "disclaimer": DISCLAIMER,
        "algorithmVersion": SURFACE_ALGORITHM_VERSION,
        "generatedAt": generated_at,
        "captureSetId": capture_set_id,
        "sourceViewCount": len(views),
        "acceptedViewCount": len(accepted),
        "qualityScore": quality_score,
        "qualityThresholds": {
            "minimumAcceptedViews": 3,
            "minimumUniqueAngles": 3,
            "minimumDimensionPixels": 64,
            "minimumExposureScore": 0.25,
            "minimumContrastScore": 0.05,
            "minimumSharpnessScore": 0.08,
        },
        "views": views,
        "regions": regions,
        "calibrationEvidence": {
            "calibrationId": calibration_id,
            "status": (
                "reference_received_unverified" if calibration_id else "not_provided"
            ),
            "physicalScaleUsed": False,
            "millimeterMeasurementsProduced": False,
            "limitation": (
                "A calibration reference was recorded but cannot be validated "
                "from an ID alone."
                if calibration_id
                else "No calibration reference was provided."
            ),
        },
        "limitations": [
            "The geometry is a standard region map; captures change coverage "
            "and color summaries, not anatomy.",
            "Image color varies with lighting and camera processing.",
            "No physical-size or millimeter measurement is produced.",
        ],
    }
    if len(accepted) < 3:
        manifest["status"] = "abstained"
        manifest["abstentionReasons"] = ["fewer_than_three_usable_views"]
        return SurfaceAbstention(
            reason_code="insufficient_usable_reconstruction_views",
            manifest=manifest,
        )
    if len(unique_angles) < 3:
        manifest["status"] = "abstained"
        manifest["abstentionReasons"] = ["fewer_than_three_unique_angles"]
        return SurfaceAbstention(
            reason_code="insufficient_reconstruction_angle_coverage",
            manifest=manifest,
        )
    manifest["status"] = "complete"
    manifest["abstentionReasons"] = []
    artifact = _build_glb(manifest)
    return LocalArtifact(
        data=artifact,
        filename=f"oral-observation-surface-{capture_set_id}.glb",
        media_type="model/gltf-binary",
        sha256=hashlib.sha256(artifact).hexdigest(),
        manifest=manifest,
    )


def build_observation_surface(
    sources: list[SourceView],
    *,
    capture_set_id: str,
    calibration_id: str | None,
    generated_at: str,
) -> LocalArtifact | SurfaceAbstention:
    return build_observation_surface_from_evidence(
        [inspect_source_view(source) for source in sources],
        capture_set_id=capture_set_id,
        calibration_id=calibration_id,
        generated_at=generated_at,
    )


def _font(
    size: int, *, bold: bool = False
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    try:
        return ImageFont.truetype(name, size=size)
    except OSError:
        return ImageFont.load_default()


def _draw_wrapped(
    draw: ImageDraw.ImageDraw,
    text: str,
    *,
    xy: tuple[int, int],
    font: ImageFont.ImageFont,
    fill: str,
    width: int,
    spacing: int = 12,
) -> None:
    average_character_width = max(
        8, int(draw.textlength("ABCDEFGHIJKLMNOPQRSTUVWXYZ", font=font) / 26)
    )
    wrapped = textwrap.fill(text, width=max(18, width // average_character_width))
    draw.multiline_text(xy, wrapped, font=font, fill=fill, spacing=spacing)


def _render_slide(
    *, title: str, body: str, caption: str, index: int, total: int
) -> Image.Image:
    image = Image.new("RGB", (1280, 720), "#F4F8F6")
    draw = ImageDraw.Draw(image)
    title_font = _font(48, bold=True)
    body_font = _font(28)
    label_font = _font(19, bold=True)
    caption_font = _font(22, bold=True)
    draw.rectangle((0, 0, 1280, 14), fill="#0B716C")
    draw.text((72, 54), "OralSight", font=label_font, fill="#0B716C")
    draw.text((72, 106), title, font=title_font, fill="#102A43")
    _draw_wrapped(
        draw,
        body,
        xy=(72, 196),
        font=body_font,
        fill="#365568",
        width=800,
        spacing=16,
    )
    center_x, center_y = 1040, 275
    region_positions = [
        (center_x, center_y - 110),
        (center_x, center_y + 100),
        (center_x - 120, center_y),
        (center_x + 120, center_y),
        (center_x, center_y - 55),
        (center_x, center_y + 50),
        (center_x - 65, center_y - 20),
        (center_x + 65, center_y + 18),
    ]
    for position_index, (x, y) in enumerate(region_positions):
        radius = 29 if position_index < index * 2 else 22
        color = "#0B716C" if position_index < index * 2 else "#C9D8E0"
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=color)
    draw.rounded_rectangle((52, 558, 1228, 666), radius=18, fill="#102A43")
    _draw_wrapped(
        draw,
        caption,
        xy=(78, 579),
        font=caption_font,
        fill="#FFFFFF",
        width=1120,
        spacing=8,
    )
    draw.text(
        (1118, 52),
        f"{index + 1} / {total}",
        font=label_font,
        fill="#536A7C",
    )
    draw.text((72, 682), DISCLAIMER, font=label_font, fill="#7A4D00")
    return image


REGION_DISPLAY_NAMES: dict[MouthRegion, str] = {
    MouthRegion.DORSAL_TONGUE: "Top of tongue",
    MouthRegion.VENTRAL_TONGUE: "Under the tongue",
    MouthRegion.LEFT_BUCCAL_MUCOSA: "Left inner cheek",
    MouthRegion.RIGHT_BUCCAL_MUCOSA: "Right inner cheek",
    MouthRegion.UPPER_LIP: "Upper inner lip",
    MouthRegion.LOWER_LIP: "Lower inner lip",
    MouthRegion.UPPER_DENTAL_ARCH: "Upper dental arch",
    MouthRegion.LOWER_DENTAL_ARCH: "Lower dental arch",
}

GUIDANCE_COPY: dict[str, tuple[str, str, str]] = {
    "neutral_seek_care_information": (
        "When to seek care",
        "A photo cannot determine the cause of a mouth change. Contact a dentist "
        "or medical professional if an area persists, changes, worries you, or "
        "comes with significant symptoms.",
        "Use the full report to share dates, symptoms, images, and questions.",
    ),
    "retake_for_image_quality": (
        "A clearer image is needed",
        "The selected image did not provide enough reliable visual detail. Follow "
        "the capture guide and retake it in even light before comparing it.",
        "No visual-change conclusion is shown from an image that failed "
        "quality checks.",
    ),
    "continue_user_selected_tracking": (
        "Your saved follow-up",
        "The reminder shown in OralSight was chosen by the user. Do not wait for "
        "another scan if the area worsens or you want professional advice sooner.",
        "Tracking photos can support a conversation; they do not replace "
        "an examination.",
    ),
    "professional_review_suggested": (
        "Professional review suggested",
        "The approved review rules found information that supports arranging a "
        "professional review. The image model did not make this care decision.",
        "Bring the report to a dentist or medical professional who can examine "
        "the area.",
    ),
    "prompt_professional_review_suggested": (
        "Prompt professional review suggested",
        "The approved review rules found information that supports contacting a "
        "dentist or medical professional promptly. The image model did not make "
        "this care decision.",
        "If symptoms feel severe or urgent, use appropriate local urgent or "
        "emergency care.",
    ),
}


def _evidence_panel(
    data: bytes,
    *,
    mask: VideoCandidateMask | None,
    label: str,
    size: tuple[int, int],
) -> Image.Image:
    try:
        with Image.open(BytesIO(data)) as opened:
            source = ImageOps.exif_transpose(opened).convert("RGB")
    except (OSError, UnidentifiedImageError, Image.DecompressionBombError) as exc:
        raise RuntimeError("local_video_source_invalid") from exc
    width, height = size
    panel = Image.new("RGB", size, "#102A43")
    source.thumbnail((width - 16, height - 52), Image.Resampling.LANCZOS)
    offset_x = (width - source.width) // 2
    offset_y = 44 + (height - 44 - source.height) // 2
    panel.paste(source, (offset_x, offset_y))
    overlay = Image.new("RGBA", size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    if mask is not None:
        points = [
            (
                offset_x + x * source.width,
                offset_y + y * source.height,
            )
            for x, y in mask.polygon
        ]
        overlay_draw.polygon(points, fill=(255, 193, 77, 38))
        overlay_draw.line([*points, points[0]], fill="#FFC14D", width=5, joint="curve")
    panel = Image.alpha_composite(panel.convert("RGBA"), overlay).convert("RGB")
    panel_draw = ImageDraw.Draw(panel)
    panel_draw.text((16, 11), label, font=_font(20, bold=True), fill="#FFFFFF")
    return panel


def _observation_caption(observation: SummaryVideoObservation) -> str:
    if observation.comparable and observation.normalized_change is not None:
        percent = observation.normalized_change * 100
        direction = (
            "increased"
            if percent > 0
            else "decreased"
            if percent < 0
            else "did not change"
        )
        confidence = round((observation.registration_confidence or 0) * 100)
        amount = f" by {abs(percent):.1f}%" if percent else ""
        return (
            f"Confirmed comparison: image-relative area {direction}{amount}. "
            f"Registration confidence {confidence}%."
        )
    if observation.baseline_image is not None:
        return (
            "A prior capture exists, but the comparison did not pass every "
            "comparability gate. No change value is shown."
        )
    return (
        "This is the selected current observation. A later confirmed, comparable "
        "scan is needed before showing change."
    )


def _render_observation_slide(
    observation: SummaryVideoObservation,
    *,
    sources: dict[UUID, bytes],
    index: int,
    total: int,
) -> Image.Image:
    image = Image.new("RGB", (1280, 720), "#F4F8F6")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 1280, 14), fill="#0B716C")
    draw.text((62, 43), "OralSight", font=_font(19, bold=True), fill="#0B716C")
    draw.text(
        (62, 82),
        REGION_DISPLAY_NAMES[observation.region],
        font=_font(42, bold=True),
        fill="#102A43",
    )
    draw.text(
        (1125, 48),
        f"{index + 1} / {total}",
        font=_font(19, bold=True),
        fill="#536A7C",
    )

    current = sources.get(observation.current_image.asset_id)
    if current is None:
        raise RuntimeError("local_video_source_missing")
    if observation.baseline_image is not None:
        baseline = sources.get(observation.baseline_image.asset_id)
        if baseline is None:
            raise RuntimeError("local_video_source_missing")
        baseline_panel = _evidence_panel(
            baseline,
            mask=observation.baseline_candidate_mask,
            label=f"Earlier · {observation.baseline_observed_at:%b %d, %Y}",
            size=(555, 325),
        )
        current_panel = _evidence_panel(
            current,
            mask=observation.current_candidate_mask,
            label=f"Current · {observation.current_observed_at:%b %d, %Y}",
            size=(555, 325),
        )
        image.paste(baseline_panel, (62, 150))
        image.paste(current_panel, (663, 150))
    else:
        current_panel = _evidence_panel(
            current,
            mask=observation.current_candidate_mask,
            label=f"Current · {observation.current_observed_at:%b %d, %Y}",
            size=(650, 325),
        )
        image.paste(current_panel, (315, 150))

    details = [f"Image quality {round(observation.quality_score * 100)}%"]
    if observation.appearance_label is not None:
        details.append(f"Released visual label: {observation.appearance_label}")
    if observation.estimated_area_mm2 is not None:
        details.append(
            f"Calibrated area estimate: {observation.estimated_area_mm2:.1f} mm²"
        )
    elif observation.current_candidate_mask is not None:
        details.append(
            "Image-relative area: "
            f"{observation.current_candidate_mask.normalized_area * 100:.2f}%"
        )
    draw.text(
        (62, 500),
        "  ·  ".join(details),
        font=_font(20, bold=True),
        fill="#365568",
    )
    draw.rounded_rectangle((52, 548, 1228, 666), radius=18, fill="#102A43")
    _draw_wrapped(
        draw,
        _observation_caption(observation),
        xy=(78, 573),
        font=_font(22, bold=True),
        fill="#FFFFFF",
        width=1120,
        spacing=8,
    )
    draw.text((62, 682), DISCLAIMER, font=_font(19, bold=True), fill="#7A4D00")
    return image


def _encode_slides(
    slides: list[Image.Image], *, duration_seconds: int, directory: Path
) -> bytes:
    slide_paths: list[Path] = []
    for index, slide in enumerate(slides):
        path = directory / f"slide-{index:02d}.png"
        slide.save(path, format="PNG", optimize=True)
        slide_paths.append(path)
    transition_seconds = 0.45 if len(slides) > 1 else 0.0
    segment_seconds = (duration_seconds + transition_seconds * (len(slides) - 1)) / len(
        slides
    )
    command = [imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-loglevel", "error"]
    for path in slide_paths:
        command.extend(
            [
                "-framerate",
                "24",
                "-loop",
                "1",
                "-t",
                f"{segment_seconds:.6f}",
                "-i",
                str(path),
            ]
        )
    filters = [
        f"[{index}:v]scale=1280:720,format=yuv420p,settb=AVTB,"
        f"setpts=PTS-STARTPTS,fps=24[v{index}]"
        for index in range(len(slides))
    ]
    current_label = "v0"
    for index in range(1, len(slides)):
        next_label = f"x{index}"
        offset = index * (segment_seconds - transition_seconds)
        filters.append(
            f"[{current_label}][v{index}]xfade=transition=fade:"
            f"duration={transition_seconds:.6f}:offset={offset:.6f}[{next_label}]"
        )
        current_label = next_label
    filters.append(f"[{current_label}]format=yuv420p[video]")
    output_path = directory / "summary.mp4"
    command.extend(
        [
            "-filter_complex",
            ";".join(filters),
            "-map",
            "[video]",
            "-t",
            str(duration_seconds),
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            "-map_metadata",
            "-1",
            "-metadata",
            "creation_time=1970-01-01T00:00:00Z",
            "-an",
            "-y",
            str(output_path),
        ]
    )
    try:
        subprocess.run(  # noqa: S603 - fixed arguments and no shell
            command,
            check=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=120,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError("local_video_render_failed") from exc
    return output_path.read_bytes()


def build_summary_video(
    payload: SummaryVideoPayload,
    *,
    sources: dict[UUID, bytes],
    generated_at: str,
) -> LocalArtifact:
    slide_count = len(payload.selected_observations) + 2
    slides = [
        _render_slide(
            title="Your selected scan summary",
            body=(
                f"This private video contains {len(payload.selected_observations)} "
                "selected observation"
                f"{'s' if len(payload.selected_observations) != 1 else ''} from "
                "the saved scan record. Yellow lines mark candidate boundaries."
            ),
            caption=(
                "Only confirmed, comparable pairs show a change value. Open the "
                "full report for complete provenance and limitations."
            ),
            index=0,
            total=slide_count,
        )
    ]
    slides.extend(
        _render_observation_slide(
            observation,
            sources=sources,
            index=index,
            total=slide_count,
        )
        for index, observation in enumerate(payload.selected_observations, start=1)
    )
    guidance_title, guidance_body, guidance_caption = GUIDANCE_COPY[
        payload.guidance.code
    ]
    slides.append(
        _render_slide(
            title=guidance_title,
            body=guidance_body,
            caption=guidance_caption,
            index=slide_count - 1,
            total=slide_count,
        )
    )
    with TemporaryDirectory(prefix="oralsight-video-") as temporary:
        temp = Path(temporary)
        data = _encode_slides(
            slides, duration_seconds=payload.duration_seconds, directory=temp
        )

    manifest: dict[str, Any] = {
        "schemaVersion": "oralsight.summary-video.v2",
        "rendererVersion": VIDEO_RENDERER_VERSION,
        "templateVersion": payload.template_version,
        "generatedAt": generated_at,
        "scanSessionId": str(payload.scan_session_id),
        "reportId": str(payload.report_id),
        "durationSeconds": payload.duration_seconds,
        "captionsIncluded": True,
        "captionMode": "burned_in",
        "audioRequested": payload.include_audio,
        "audioIncluded": False,
        "disclaimer": DISCLAIMER,
        "notForDiagnosis": True,
        "sourceDetail": "selected_hash_verified_observation_evidence",
        "guidance": payload.guidance.model_dump(mode="json", by_alias=True),
        "observations": [
            {
                "observationId": str(observation.observation_id),
                "region": observation.region.value,
                "currentCaptureId": str(observation.current_capture_id),
                "currentAssetId": str(observation.current_image.asset_id),
                "currentAssetSha256": observation.current_image.sha256,
                "currentCandidateOutlineIncluded": (
                    observation.current_candidate_mask is not None
                ),
                "baselineCaptureId": (
                    str(observation.baseline_capture_id)
                    if observation.baseline_capture_id is not None
                    else None
                ),
                "baselineAssetId": (
                    str(observation.baseline_image.asset_id)
                    if observation.baseline_image is not None
                    else None
                ),
                "baselineAssetSha256": (
                    observation.baseline_image.sha256
                    if observation.baseline_image is not None
                    else None
                ),
                "baselineCandidateOutlineIncluded": (
                    observation.baseline_candidate_mask is not None
                ),
                "userConfirmedMatch": observation.user_confirmed_match,
                "comparable": observation.comparable,
                "registrationConfidence": observation.registration_confidence,
                "normalizedChange": observation.normalized_change,
                "measurementLabel": observation.measurement_label,
            }
            for observation in payload.selected_observations
        ],
        "limitations": [
            "The video contains only the observations selected for this export.",
            "Candidate outlines and image-relative changes are approximate.",
            "Open the report for complete provenance, uncertainty, and limitations.",
        ],
    }
    return LocalArtifact(
        data=data,
        filename=f"oralsight-summary-{payload.scan_session_id}.mp4",
        media_type="video/mp4",
        sha256=hashlib.sha256(data).hexdigest(),
        manifest=manifest,
    )

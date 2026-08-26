"""Generate printable OralSight calibration cards at an exact 300 DPI scale."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
from PIL import Image, ImageDraw, ImageFont

DPI = 300
MM_PER_INCH = 25.4
MARKER_SIDE_MM = 20.0
MARKER_ID = 17
CARD_VERSION = "oralsight-calibration-v1"
REFERENCE_BAR_MM = 50.0
NEUTRAL_PATCH_VALUES = (35, 100, 170, 235)


def _px(mm: float) -> int:
    return round(mm / MM_PER_INCH * DPI)


def _font(
    size: int, *, bold: bool = False
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = (
        ("C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf"),
        (
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
            if bold
            else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        ),
        ("/System/Library/Fonts/SFNS.ttf"),
    )
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _fit_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    *,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    max_width: int,
) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if draw.textbbox((0, 0), candidate, font=font)[2] <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _qr_image(payload: str, side_px: int) -> Image.Image:
    parameters = cv2.QRCodeEncoder_Params()
    parameters.version = 0
    parameters.correction_level = cv2.QRCodeEncoder_CORRECT_LEVEL_M
    encoder = cv2.QRCodeEncoder_create(parameters)
    encoded = encoder.encode(payload)
    quiet = max(8, encoded.shape[0] // 8)
    encoded = cv2.copyMakeBorder(
        encoded,
        quiet,
        quiet,
        quiet,
        quiet,
        cv2.BORDER_CONSTANT,
        value=255,
    )
    resized = cv2.resize(encoded, (side_px, side_px), interpolation=cv2.INTER_NEAREST)
    return Image.fromarray(resized).convert("L")


def build_card(*, page_width_mm: float, page_height_mm: float) -> Image.Image:
    width = _px(page_width_mm)
    height = _px(page_height_mm)
    canvas = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(canvas)
    margin = _px(16)
    ink = (25, 32, 38)
    teal = (24, 112, 110)
    muted = (75, 85, 92)

    title_font = _font(_px(5.0), bold=True)
    body_font = _font(_px(3.1))
    small_font = _font(_px(2.4))
    small_bold = _font(_px(2.5), bold=True)

    draw.text((margin, margin), "OralSight calibration card", fill=ink, font=title_font)
    subtitle_y = margin + _px(8)
    draw.text(
        (margin, subtitle_y),
        "For optional approximate image measurements",
        fill=muted,
        font=body_font,
    )
    draw.line(
        (margin, subtitle_y + _px(7), width - margin, subtitle_y + _px(7)),
        fill=(205, 213, 216),
        width=max(1, _px(0.25)),
    )

    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    marker_side = _px(MARKER_SIDE_MM)
    marker_array = cv2.aruco.generateImageMarker(dictionary, MARKER_ID, marker_side)
    marker = Image.fromarray(marker_array).convert("L")
    quiet_zone = _px(4)
    marker_panel_side = marker_side + quiet_zone * 2
    marker_panel_x = margin
    marker_panel_y = subtitle_y + _px(17)
    draw.rectangle(
        (
            marker_panel_x,
            marker_panel_y,
            marker_panel_x + marker_panel_side,
            marker_panel_y + marker_panel_side,
        ),
        fill="white",
        outline=(190, 198, 202),
        width=max(1, _px(0.2)),
    )
    canvas.paste(marker, (marker_panel_x + quiet_zone, marker_panel_y + quiet_zone))
    draw.text(
        (marker_panel_x, marker_panel_y + marker_panel_side + _px(2)),
        "20 mm reference marker",
        fill=ink,
        font=small_bold,
    )

    payload = json.dumps(
        {
            "schema": "oralsight_calibration_card",
            "version": CARD_VERSION,
            "marker_dictionary": "DICT_4X4_50",
            "marker_id": MARKER_ID,
            "marker_side_mm": MARKER_SIDE_MM,
            "reference_bar_mm": REFERENCE_BAR_MM,
        },
        separators=(",", ":"),
        sort_keys=True,
    )
    qr_side = _px(26)
    qr = _qr_image(payload, qr_side)
    qr_x = width - margin - qr_side
    qr_y = marker_panel_y
    canvas.paste(qr, (qr_x, qr_y))
    draw.text(
        (qr_x, qr_y + qr_side + _px(2)), "Card details", fill=ink, font=small_bold
    )

    patches_x = marker_panel_x + marker_panel_side + _px(14)
    patches_y = marker_panel_y + _px(3)
    draw.text((patches_x, patches_y), "Neutral reference", fill=ink, font=small_bold)
    patch_side = _px(9)
    for index, value in enumerate(NEUTRAL_PATCH_VALUES):
        left = patches_x + index * (patch_side + _px(2))
        top = patches_y + _px(7)
        draw.rectangle(
            (left, top, left + patch_side, top + patch_side),
            fill=(value, value, value),
            outline=(25, 32, 38),
            width=max(1, _px(0.18)),
        )

    bar_y = marker_panel_y + marker_panel_side + _px(18)
    bar_x = margin
    bar_width = _px(REFERENCE_BAR_MM)
    draw.line((bar_x, bar_y, bar_x + bar_width, bar_y), fill=ink, width=_px(0.5))
    for position in (0, bar_width):
        draw.line(
            (bar_x + position, bar_y - _px(2), bar_x + position, bar_y + _px(2)),
            fill=ink,
            width=_px(0.5),
        )
    draw.text(
        (bar_x, bar_y + _px(3)),
        "This line must measure exactly 50 mm",
        fill=ink,
        font=small_bold,
    )

    instructions_y = bar_y + _px(18)
    draw.rounded_rectangle(
        (margin, instructions_y, width - margin, instructions_y + _px(55)),
        radius=_px(3),
        fill=(239, 247, 246),
        outline=(174, 211, 207),
        width=max(1, _px(0.25)),
    )
    draw.text(
        (margin + _px(6), instructions_y + _px(6)),
        "Before use",
        fill=teal,
        font=small_bold,
    )
    instructions = (
        "Print at 100% or Actual size. Do not use Fit to page. Check the 50 mm line "
        "with a ruler. Keep the card outside the mouth and close to the area being "
        "photographed. Do not let the paper touch tissue or an observation."
    )
    text_y = instructions_y + _px(14)
    for line in _fit_text(
        draw,
        instructions,
        font=body_font,
        max_width=width - margin * 2 - _px(12),
    ):
        draw.text((margin + _px(6), text_y), line, fill=ink, font=body_font)
        text_y += _px(5.2)

    footer_y = height - margin - _px(14)
    draw.line(
        (margin, footer_y, width - margin, footer_y), fill=(205, 213, 216), width=1
    )
    draw.text((margin, footer_y + _px(3)), CARD_VERSION, fill=muted, font=small_font)
    disclaimer = "Estimated size only. This result is not a diagnosis."
    disclaimer_width = draw.textbbox((0, 0), disclaimer, font=small_font)[2]
    draw.text(
        (width - margin - disclaimer_width, footer_y + _px(3)),
        disclaimer,
        fill=muted,
        font=small_font,
    )
    return canvas


def generate(output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    generated: list[Path] = []
    for name, width_mm, height_mm in (
        ("a4", 210.0, 297.0),
        ("letter", 215.9, 279.4),
    ):
        card = build_card(page_width_mm=width_mm, page_height_mm=height_mm)
        pdf_path = output_dir / f"oralsight-calibration-{name}.pdf"
        card.save(pdf_path, "PDF", resolution=DPI, quality=100)
        generated.append(pdf_path)
        if name == "a4":
            preview_path = output_dir / "oralsight-calibration-preview.png"
            preview = card.copy()
            preview.thumbnail((_px(105), _px(148.5)), Image.Resampling.LANCZOS)
            preview.save(preview_path, "PNG", optimize=True)
            generated.append(preview_path)
    return generated


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("assets/mouth/calibration"),
    )
    args = parser.parse_args()
    for path in generate(args.output_dir):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Clinician-ready PDF rendering from authorized, integrity-checked records."""

from __future__ import annotations

import html
from io import BytesIO
from typing import Any

from PIL import Image as PillowImage
from PIL import ImageDraw, ImageOps, UnidentifiedImageError
from reportlab.graphics.shapes import Circle, Drawing, Rect, String
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import (
    HRFlowable,
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

DISCLAIMER = "This result is not a diagnosis."
PAGE_WIDTH, PAGE_HEIGHT = LETTER
DEFAULT_QUESTIONS = (
    "What does this area look like during an in-person examination?",
    "Would a professional photograph or another evaluation be useful?",
    "Which visible changes should prompt an earlier follow-up?",
    "When, if at all, should this area be checked again?",
)
REGION_LABELS = {
    "dorsal_tongue": "Top of tongue",
    "ventral_tongue": "Under tongue",
    "left_buccal_mucosa": "Left inner cheek",
    "right_buccal_mucosa": "Right inner cheek",
    "upper_lip": "Upper inner lip",
    "lower_lip": "Lower inner lip",
    "upper_dental_arch": "Upper dental arch",
    "lower_dental_arch": "Lower dental arch",
}


class ReportRenderError(ValueError):
    pass


def _safe(value: Any) -> str:
    if value is None or value == "":
        return "Not provided"
    return html.escape(str(value), quote=True)


def _human(value: Any) -> str:
    return _safe(str(value).replace("_", " ").strip().title())


def _percent(value: Any) -> str:
    if isinstance(value, int | float):
        return f"{float(value):.0%}"
    return "Unavailable"


def _overlay_capture(
    image_bytes: bytes, candidate_mask: dict[str, Any]
) -> tuple[bytes, int, int]:
    """Decode one verified image and paint its normalized candidate geometry."""

    try:
        with PillowImage.open(BytesIO(image_bytes)) as probe:
            probe.verify()
        with PillowImage.open(BytesIO(image_bytes)) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
    except (UnidentifiedImageError, OSError, PillowImage.DecompressionBombError) as exc:
        raise ReportRenderError("capture_image_decode_failed") from exc
    if image.width <= 0 or image.height <= 0 or image.width * image.height > 40_000_000:
        raise ReportRenderError("capture_image_dimensions_invalid")
    image.thumbnail((1200, 900), PillowImage.Resampling.LANCZOS)
    overlay = PillowImage.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay, "RGBA")
    polygon = candidate_mask.get("polygon") or []
    points: list[tuple[float, float]] = []
    for point in polygon:
        if (
            isinstance(point, list | tuple)
            and len(point) == 2
            and all(isinstance(value, int | float) for value in point)
        ):
            x, y = float(point[0]), float(point[1])
            if 0 <= x <= 1 and 0 <= y <= 1:
                points.append((x * image.width, y * image.height))
    if len(points) >= 3:
        draw.polygon(
            points, fill=(255, 184, 77, 72), outline=(191, 70, 48, 255), width=5
        )
    bounds = candidate_mask.get("boundingBox")
    if (
        isinstance(bounds, list | tuple)
        and len(bounds) == 4
        and all(isinstance(value, int | float) for value in bounds)
    ):
        x, y, width, height = (float(value) for value in bounds)
        if min(x, y, width, height) >= 0 and x + width <= 1 and y + height <= 1:
            draw.rectangle(
                (
                    x * image.width,
                    y * image.height,
                    (x + width) * image.width,
                    (y + height) * image.height,
                ),
                outline=(191, 70, 48, 255),
                width=4,
            )
    composited = PillowImage.alpha_composite(image.convert("RGBA"), overlay).convert(
        "RGB"
    )
    output = BytesIO()
    composited.save(output, format="PNG", optimize=True)
    return output.getvalue(), composited.width, composited.height


def _oral_map(observations: list[dict[str, Any]]) -> Drawing:
    drawing = Drawing(480, 250)
    observed = {str(item.get("region")) for item in observations}
    positions = {
        "upper_lip": (25, 185),
        "lower_lip": (245, 185),
        "left_buccal_mucosa": (25, 125),
        "right_buccal_mucosa": (245, 125),
        "upper_dental_arch": (25, 65),
        "lower_dental_arch": (245, 65),
        "dorsal_tongue": (25, 5),
        "ventral_tongue": (245, 5),
    }
    for region, (x, y) in positions.items():
        active = region in observed
        drawing.add(
            Rect(
                x,
                y,
                205,
                48,
                rx=10,
                ry=10,
                fillColor=HexColor("#DDF4EE" if active else "#F2F1ED"),
                strokeColor=HexColor("#0B706B" if active else "#C9C7C0"),
                strokeWidth=1.5,
            )
        )
        drawing.add(
            String(
                x + 14,
                y + 28,
                REGION_LABELS[region],
                fontName="Helvetica-Bold",
                fontSize=9,
                fillColor=HexColor("#173D3A"),
            )
        )
        drawing.add(
            String(
                x + 14,
                y + 12,
                "Observation included" if active else "No selected observation",
                fontName="Helvetica",
                fontSize=7.5,
                fillColor=HexColor("#586560"),
            )
        )
        if active:
            drawing.add(
                Circle(
                    x + 188,
                    y + 24,
                    6,
                    fillColor=HexColor("#E9A23B"),
                    strokeColor=HexColor("#76501D"),
                )
            )
    return drawing


def _styles():
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            "ReportTitle",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=24,
            leading=28,
            textColor=HexColor("#113D3A"),
            alignment=TA_LEFT,
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            "Section",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=15,
            leading=19,
            textColor=HexColor("#113D3A"),
            spaceBefore=14,
            spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle(
            "Subsection",
            parent=styles["Heading3"],
            fontName="Helvetica-Bold",
            fontSize=11.5,
            leading=15,
            textColor=HexColor("#184F4B"),
            spaceAfter=5,
        )
    )
    styles.add(
        ParagraphStyle(
            "BodySmall",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=12,
            textColor=HexColor("#303735"),
            spaceAfter=4,
        )
    )
    styles.add(
        ParagraphStyle(
            "Fine",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=7.5,
            leading=10,
            textColor=HexColor("#5A6461"),
        )
    )
    styles.add(
        ParagraphStyle(
            "Warning",
            parent=styles["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            textColor=HexColor("#6E4300"),
            backColor=HexColor("#FFF2D8"),
            borderColor=HexColor("#D79B31"),
            borderWidth=1,
            borderPadding=9,
            spaceAfter=14,
        )
    )
    styles.add(
        ParagraphStyle(
            "CenterFine",
            parent=styles["Fine"],
            alignment=TA_CENTER,
        )
    )
    return styles


def _footer(canvas, document) -> None:
    canvas.saveState()
    canvas.setStrokeColor(HexColor("#D8D5CF"))
    canvas.line(document.leftMargin, 36, PAGE_WIDTH - document.rightMargin, 36)
    canvas.setFillColor(HexColor("#4B4A47"))
    canvas.setFont("Helvetica-Bold", 8)
    canvas.drawString(document.leftMargin, 22, DISCLAIMER)
    page = f"Page {document.page}"
    canvas.setFont("Helvetica", 8)
    canvas.drawString(
        PAGE_WIDTH - document.rightMargin - stringWidth(page, "Helvetica", 8),
        22,
        page,
    )
    canvas.restoreState()


def _key_value_table(rows: list[tuple[str, Any]], styles) -> Table:
    values = [
        [
            Paragraph(f"<b>{_safe(label)}</b>", styles["BodySmall"]),
            Paragraph(_safe(value), styles["BodySmall"]),
        ]
        for label, value in rows
    ]
    table = Table(values, colWidths=[1.62 * inch, 5.05 * inch], hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BACKGROUND", (0, 0), (0, -1), HexColor("#F2F7F5")),
                ("GRID", (0, 0), (-1, -1), 0.35, HexColor("#D6DEDB")),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


def build_report_pdf(
    *,
    report_id: str,
    scan_id: str,
    created_at: str,
    account: dict[str, Any],
    consent: dict[str, Any],
    scan: dict[str, Any],
    patient_profile: dict[str, Any] | None,
    intake_summary: dict[str, Any] | None,
    observations: list[dict[str, Any]],
    comparisons: list[dict[str, Any]],
    appointment_questions: list[str],
    include_experimental: bool,
) -> bytes:
    """Build a bounded PDF; inputs must already be authorized and hash-verified."""

    styles = _styles()
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=LETTER,
        rightMargin=42,
        leftMargin=42,
        topMargin=42,
        bottomMargin=52,
        title="OralSight oral observation report",
        author="OralSight",
        subject="Non-diagnostic oral observation summary",
    )
    story: list[Any] = [
        Paragraph("Oral observation report", styles["ReportTitle"]),
        Paragraph(
            "A structured record for discussion with a dental or medical professional.",
            styles["BodyText"],
        ),
        Spacer(1, 8),
        Paragraph(DISCLAIMER, styles["Warning"]),
        _key_value_table(
            [
                ("Created", created_at),
                ("Report reference", report_id),
                ("Scan reference", scan_id),
                ("Account reference", account.get("reference")),
                ("Account created", account.get("createdAt")),
                ("Capture protocol", _human(scan.get("protocol"))),
                ("Accepted regions", f"{scan.get('acceptedRegionCount', 0)} of 8"),
            ],
            styles,
        ),
        Paragraph("Consent and data use", styles["Section"]),
        _key_value_table(
            [
                ("Product consent", "Active at report request"),
                ("Consent document", consent.get("documentId")),
                ("Consent version", consent.get("documentVersion")),
                ("Consent text SHA-256", consent.get("documentSha256")),
                ("Accepted", consent.get("acceptedAt")),
                (
                    "Age range",
                    _human((patient_profile or {}).get("ageRange")),
                ),
                (
                    "Assisted use",
                    (
                        "Yes"
                        if (patient_profile or {}).get("assisted") is True
                        else "No"
                        if (patient_profile or {}).get("assisted") is False
                        else "Not provided"
                    ),
                ),
            ],
            styles,
        ),
    ]
    story.append(Paragraph("Symptoms and intake", styles["Section"]))
    if intake_summary is None:
        story.append(
            Paragraph(
                "No symptom or intake summary was authorized for this cloud report.",
                styles["BodySmall"],
            )
        )
    else:
        symptoms = intake_summary.get("symptoms") or []
        story.append(
            _key_value_table(
                [
                    ("First noticed", intake_summary.get("firstNoticed")),
                    (
                        "Approximate duration",
                        (
                            f"{intake_summary['durationDays']} days"
                            if intake_summary.get("durationDays") is not None
                            else "Not provided"
                        ),
                    ),
                    ("Reported symptoms", ", ".join(symptoms) or "None reported"),
                    ("Reported change", _human(intake_summary.get("change"))),
                    (
                        "Bleeding frequency",
                        _human(intake_summary.get("bleedingFrequency")),
                    ),
                    ("Bleeding duration", intake_summary.get("bleedingDuration")),
                    (
                        "Tobacco exposure",
                        _human(intake_summary.get("tobaccoExposure")),
                    ),
                    (
                        "Alcohol exposure",
                        _human(intake_summary.get("alcoholExposure")),
                    ),
                    (
                        "Previous conditions",
                        intake_summary.get("previousConditions") or "None reported",
                    ),
                    (
                        "Professionally examined",
                        "Yes" if intake_summary.get("professionallyExamined") else "No",
                    ),
                ],
                styles,
            )
        )
    story.extend(
        [
            Paragraph("Oral observation map", styles["Section"]),
            Paragraph(
                "This is a generic eight-region location map. It is not a personalized anatomical model. Pins use a named mesh, region-relative UV coordinates, and a versioned asset when those fields are available.",
                styles["BodySmall"],
            ),
            _oral_map(observations),
            Paragraph("Selected observations", styles["Section"]),
        ]
    )

    for index, item in enumerate(observations, start=1):
        region = str(item.get("region"))
        overlay, width, height = _overlay_capture(
            item["imageBytes"], item.get("candidateMask") or {}
        )
        image_width = 2.35 * inch
        image_height = min(1.8 * inch, image_width * height / width)
        figure = [
            Image(BytesIO(overlay), width=image_width, height=image_height),
            Paragraph(
                "Sanitized analysis capture with candidate mask overlay.",
                styles["CenterFine"],
            ),
        ]
        descriptors = item.get("descriptors") or {}
        uncertainty = item.get("uncertainty") or {}
        calibration = item.get("calibration") or {}
        details: list[Any] = [
            Paragraph(
                f"{index}. {_safe(REGION_LABELS.get(region, _human(region)))}",
                styles["Subsection"],
            ),
            Paragraph(
                f"<b>Captured:</b> {_safe(item.get('capturedAt'))}<br/>"
                f"<b>Anatomical site:</b> {_human(item.get('anatomicalSite'))}<br/>"
                f"<b>Quality accepted:</b> {'Yes' if item.get('qualityAccepted') else 'No'}<br/>"
                f"<b>Approximate normalized area:</b> {_safe(descriptors.get('normalizedArea'))}<br/>"
                f"<b>Shape:</b> perimeter {_safe(descriptors.get('perimeter'))}; border irregularity {_safe(descriptors.get('borderIrregularity'))}<br/>"
                f"<b>Color / texture:</b> redness {_safe(descriptors.get('meanRedness'))}; brightness {_safe(descriptors.get('meanBrightness'))}; texture contrast {_safe(descriptors.get('textureContrast'))}",
                styles["BodySmall"],
            ),
            Paragraph(
                f"<b>Overall confidence:</b> {_percent(uncertainty.get('overallConfidence'))}<br/>"
                f"<b>Image-quality confidence:</b> {_percent(uncertainty.get('imageQualityConfidence'))}<br/>"
                f"<b>Dataset similarity:</b> {_percent(uncertainty.get('datasetSimilarity'))}<br/>"
                f"<b>Model agreement:</b> {_percent(uncertainty.get('modelAgreement'))}",
                styles["BodySmall"],
            ),
        ]
        if calibration.get("status") == "valid":
            details.append(
                Paragraph(
                    "<b>Calibrated estimate:</b> "
                    f"{_safe(calibration.get('estimatedWidthMm'))} x "
                    f"{_safe(calibration.get('estimatedHeightMm'))} mm; "
                    f"area {_safe(calibration.get('estimatedAreaMm2'))} mm2. "
                    f"Calibration confidence {_percent(calibration.get('confidence'))}.",
                    styles["BodySmall"],
                )
            )
        else:
            details.append(
                Paragraph(
                    "No valid physical calibration. Image-derived measurements are approximate and are not millimeter measurements.",
                    styles["BodySmall"],
                )
            )
        appearance = item.get("appearance")
        if appearance:
            details.append(
                Paragraph(
                    f"<b>Appearance descriptor:</b> {_safe(appearance.get('topLabel'))} ({_percent(appearance.get('confidence'))}). {_safe(appearance.get('limitation'))}",
                    styles["BodySmall"],
                )
            )
        experimental = item.get("experimental")
        if include_experimental and experimental:
            details.append(
                Paragraph(
                    f"<b>Experimental research output:</b> {_safe(experimental.get('topLabel'))} ({_percent(experimental.get('confidence'))}). {_safe(experimental.get('limitation'))}",
                    styles["BodySmall"],
                )
            )
        limitations = [
            *list(item.get("limitations") or []),
            *list(uncertainty.get("limitations") or []),
        ]
        if limitations:
            details.append(
                Paragraph(
                    "<b>Limitations:</b> "
                    + " ".join(f"• {_safe(value)}" for value in limitations[:12]),
                    styles["BodySmall"],
                )
            )
        if item.get("namedMesh"):
            uv = item.get("uvCoordinates") or []
            details.append(
                Paragraph(
                    f"<b>Map location:</b> {_safe(item.get('namedMesh'))}, UV {_safe(', '.join(str(value) for value in uv))}, asset {_safe(item.get('assetVersion'))}.",
                    styles["Fine"],
                )
            )
        details.append(
            Paragraph(
                f"<b>Provenance:</b> input {_human(item.get('inputOrigin'))}; analysis {_human(item.get('analysisOrigin'))}; capture SHA-256 {_safe(item.get('imageSha256'))}; models {_safe(', '.join(f'{key}={value}' for key, value in sorted((item.get('modelVersions') or {}).items())))}.",
                styles["Fine"],
            )
        )
        block = Table([[figure, details]], colWidths=[2.55 * inch, 4.05 * inch])
        block.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("BOX", (0, 0), (-1, -1), 0.6, HexColor("#CBD8D4")),
                    ("BACKGROUND", (0, 0), (-1, -1), HexColor("#FBFCFB")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )
        story.extend([KeepTogether([block]), Spacer(1, 10)])

    input_origins = sorted(
        {
            str(item.get("inputOrigin"))
            for item in observations
            if item.get("inputOrigin")
        }
    )
    analysis_origins = sorted(
        {
            str(item.get("analysisOrigin"))
            for item in observations
            if item.get("analysisOrigin")
        }
    )
    model_versions = {
        str(key): str(value)
        for item in observations
        for key, value in (item.get("modelVersions") or {}).items()
    }
    story.extend(
        [
            Paragraph("Input and analysis provenance", styles["Section"]),
            _key_value_table(
                [
                    ("Input origin", ", ".join(input_origins) or "Unavailable"),
                    (
                        "Analysis origin",
                        ", ".join(analysis_origins) or "Unavailable",
                    ),
                    (
                        "Model versions",
                        ", ".join(
                            f"{key}={value}"
                            for key, value in sorted(model_versions.items())
                        )
                        or "Unavailable",
                    ),
                    (
                        "Verified source hashes",
                        ", ".join(
                            str(item.get("imageSha256"))
                            for item in observations
                            if item.get("imageSha256")
                        )
                        or "Unavailable",
                    ),
                ],
                styles,
            ),
        ]
    )

    story.extend(
        [
            PageBreak(),
            Paragraph("User-confirmed timeline", styles["Section"]),
            Paragraph(
                "A change is shown only when the user confirmed the link and the stored comparison passed registration gates. Otherwise the report says that comparable data is insufficient.",
                styles["BodySmall"],
            ),
        ]
    )
    if not comparisons:
        story.append(
            Paragraph(
                "No user-confirmed comparison was selected for this report.",
                styles["BodySmall"],
            )
        )
    for index, item in enumerate(comparisons, start=1):
        comparable = item.get("comparable") is True
        change = item.get("normalizedChange") if comparable else None
        story.extend(
            [
                Paragraph(
                    f"{index}. {_safe(REGION_LABELS.get(str(item.get('region')), _human(item.get('region'))))}",
                    styles["Subsection"],
                ),
                _key_value_table(
                    [
                        ("Baseline", item.get("baselineObservedAt")),
                        ("Current", item.get("currentObservedAt")),
                        ("User confirmed", "Yes"),
                        ("Comparable", "Yes" if comparable else "No"),
                        (
                            "Approximate normalized change",
                            f"{float(change):+.1%}"
                            if isinstance(change, int | float)
                            else "Insufficient comparable data",
                        ),
                        (
                            "Registration confidence",
                            _percent(item.get("registrationConfidence")),
                        ),
                        ("Inlier ratio", _percent(item.get("inlierRatio"))),
                        (
                            "Reprojection error",
                            _percent(item.get("reprojectionErrorRatio")),
                        ),
                        (
                            "Suppression reasons",
                            ", ".join(item.get("suppressionReasons") or []) or "None",
                        ),
                        (
                            "Models",
                            ", ".join(
                                f"{key}={value}"
                                for key, value in sorted(
                                    (item.get("modelVersions") or {}).items()
                                )
                            )
                            or "Unavailable",
                        ),
                    ],
                    styles,
                ),
                Spacer(1, 9),
            ]
        )

    questions = appointment_questions or list(DEFAULT_QUESTIONS)
    story.extend(
        [
            Paragraph("Questions for an appointment", styles["Section"]),
            Paragraph(
                "Conversation prompts only; these are not clinical recommendations.",
                styles["BodySmall"],
            ),
        ]
    )
    for value in questions:
        story.append(Paragraph(f"• {_safe(value)}", styles["BodySmall"]))

    story.extend(
        [
            Paragraph("Report limitations", styles["Section"]),
            Paragraph(
                "Image observations depend on capture quality, lighting, camera angle, calibration, model release gates, and the data used to evaluate each model. A mask marks a candidate area; it does not identify a cause. Normalized change is image-relative. A calibrated estimate is still approximate. The sanitized analysis captures shown here are the cloud-held copies; local originals are not fetched or substituted.",
                styles["BodySmall"],
            ),
            HRFlowable(
                width="100%", thickness=0.7, color=HexColor("#C9D3D0"), spaceBefore=8
            ),
            Paragraph(DISCLAIMER, styles["Warning"]),
        ]
    )
    document.build(story, onFirstPage=_footer, onLaterPages=_footer)
    data = buffer.getvalue()
    buffer.close()
    if not data.startswith(b"%PDF-") or len(data) < 1_000:
        raise ReportRenderError("pdf_render_failed")
    return data

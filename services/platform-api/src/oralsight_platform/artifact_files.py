"""Safe filenames for generated artifacts."""

from __future__ import annotations


def report_filename(report_id: str, media_type: str) -> str:
    extension = {
        "application/pdf": "pdf",
        "application/json": "json",
        "text/html": "html",
    }.get(media_type, "bin")
    return f"oralsight-report-{report_id}.{extension}"

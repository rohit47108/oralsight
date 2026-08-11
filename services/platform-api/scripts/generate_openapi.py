"""Regenerate the checked public/internal platform OpenAPI contract."""

from __future__ import annotations

import json
from pathlib import Path

from oralsight_platform.main import app


def main() -> None:
    target = Path(__file__).resolve().parents[1] / "openapi.json"
    rendered = (
        json.dumps(app.openapi(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )
    target.write_text(rendered, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()

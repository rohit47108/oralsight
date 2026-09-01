"""Validate Stoma3D's Vercel configs against the live schema and repo layout."""

from __future__ import annotations

import json
import sys
import tomllib
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from jsonschema import Draft7Validator


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_URL = "https://openapi.vercel.sh/vercel.json"
CONFIG_PATHS = (
    REPOSITORY_ROOT / "vercel.json",
    REPOSITORY_ROOT / "services" / "inference" / "vercel.json",
)


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.relative_to(REPOSITORY_ROOT)} must contain an object")
    return value


def load_schema() -> dict[str, Any]:
    request = Request(SCHEMA_URL, headers={"User-Agent": "Stoma3D-CI/1"})
    with urlopen(request, timeout=20) as response:  # noqa: S310 - fixed HTTPS URL
        value = json.load(response)
    if not isinstance(value, dict):
        raise ValueError("Vercel returned a non-object configuration schema")
    return value


def validate_schema(schema: dict[str, Any], path: Path, value: dict[str, Any]) -> None:
    # Vercel currently declares Draft 4 while using later keywords. Draft 7
    # validates the shared vocabulary without rejecting that mixed declaration.
    validator = Draft7Validator(schema)
    errors = sorted(validator.iter_errors(value), key=lambda error: list(error.path))
    if not errors:
        return
    details = []
    for error in errors:
        pointer = "/".join(str(part) for part in error.absolute_path) or "<root>"
        details.append(f"  {pointer}: {error.message}")
    relative = path.relative_to(REPOSITORY_ROOT)
    raise ValueError(
        f"{relative} failed Vercel schema validation:\n" + "\n".join(details)
    )


def require_file(root: Path, relative: str, label: str) -> None:
    target = root / relative
    if not target.is_file():
        raise ValueError(f"{label} is missing: {target.relative_to(REPOSITORY_ROOT)}")


def validate_repository_contract(root_config: dict[str, Any]) -> None:
    services = root_config.get("services")
    if not isinstance(services, dict) or set(services) != {"web"}:
        raise ValueError("root vercel.json must define exactly the web service")

    web = services["web"]
    if web.get("framework") != "nextjs":
        raise ValueError("the Vercel web service framework must remain nextjs")
    if web.get("installCommand") != (
        "pnpm install --frozen-lockfile --virtual-store-dir .pnpm"
    ):
        raise ValueError(
            "the Vercel web dependency store must remain inside the repository"
        )

    web_root = REPOSITORY_ROOT / str(web.get("root", ""))
    require_file(web_root, "package.json", "web build manifest")
    require_file(web_root, "next.config.ts", "web build configuration")

    rewrites = root_config.get("rewrites")
    if not isinstance(rewrites, list) or not rewrites:
        raise ValueError("root vercel.json must expose services through rewrites")
    for rewrite in rewrites:
        destination = rewrite.get("destination") if isinstance(rewrite, dict) else None
        if isinstance(destination, dict):
            if destination.get("service") not in services:
                raise ValueError("service rewrites must target a declared service")
        elif not (
            isinstance(destination, str)
            and destination.startswith("https://stoma3d-inference.vercel.app/api/")
        ):
            raise ValueError(
                "external rewrites must target the verified Stoma3D inference origin"
            )

    expected_inference_rewrites = {
        "/api/v1/:path*": "https://stoma3d-inference.vercel.app/api/v1/:path*",
        "/api/healthz": "https://stoma3d-inference.vercel.app/api/healthz",
    }
    actual_inference_rewrites = {
        rewrite.get("source"): rewrite.get("destination")
        for rewrite in rewrites
        if isinstance(rewrite, dict) and isinstance(rewrite.get("destination"), str)
    }
    if actual_inference_rewrites != expected_inference_rewrites:
        raise ValueError(
            "inference rewrites must proxy the verified standalone deployment"
        )
    if (
        rewrites[-1].get("source") != "/(.*)"
        or rewrites[-1]["destination"].get("service") != "web"
    ):
        raise ValueError("the final Vercel rewrite must be the web catch-all")

    ignore_path = REPOSITORY_ROOT / ".vercelignore"
    ignore_rules = {
        line.strip()
        for line in ignore_path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    if "work/" not in ignore_rules or "outputs/" not in ignore_rules:
        raise ValueError("Vercel uploads must exclude work/ and outputs/")
    if "patches/" in ignore_rules:
        raise ValueError(
            "Vercel uploads must include pnpm patchedDependencies from patches/"
        )
    require_file(
        REPOSITORY_ROOT,
        "patches/image-size@1.2.1.patch",
        "patched web dependency",
    )
    require_file(
        REPOSITORY_ROOT,
        "patches/react-native-mlkit-face-detection-5.0.0.patch",
        "workspace patch manifest",
    )


def validate_standalone_inference(value: dict[str, Any]) -> None:
    inference_root = REPOSITORY_ROOT / "services" / "inference"
    project = tomllib.loads(
        (inference_root / "pyproject.toml").read_text(encoding="utf-8")
    )
    entrypoint = project.get("tool", {}).get("vercel", {}).get("entrypoint")
    if not isinstance(entrypoint, str) or ":" not in entrypoint:
        raise ValueError("standalone inference must declare a module:object entrypoint")
    module_name, object_name = entrypoint.split(":", 1)
    if not module_name or not object_name:
        raise ValueError("standalone inference entrypoint must name module and object")
    require_file(
        inference_root,
        f"{module_name.replace('.', '/')}.py",
        "standalone inference entrypoint module",
    )

    functions = value.get("functions")
    settings: dict[str, Any] = {}
    if isinstance(functions, dict):
        explicit_settings = functions.get(f"{module_name.replace('.', '/')}.py")
        wildcard_settings = functions.get("**/*.py")
        if isinstance(explicit_settings, dict):
            settings = explicit_settings
        elif isinstance(wildcard_settings, dict):
            settings = wildcard_settings
    if settings.get("maxDuration", 0) < 18:
        raise ValueError(
            "standalone inference vercel.json must cover the 18-second mobile deadline"
        )


def main() -> int:
    try:
        schema = load_schema()
        values = [load_json(path) for path in CONFIG_PATHS]
        for path, value in zip(CONFIG_PATHS, values, strict=True):
            validate_schema(schema, path, value)
        validate_repository_contract(values[0])
        validate_standalone_inference(values[1])
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Vercel configuration validation failed: {exc}", file=sys.stderr)
        return 1
    print("Vercel configuration schema and build-surface checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

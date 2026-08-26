"""Generate deterministic dependency inventory and bundled license notices.

The report is built from the checked pnpm/uv lock graphs and the license files
installed by those locked packages. Optional Python packages that cannot be
installed on the current platform remain visible in the SBOM and are called
out explicitly instead of receiving an invented license.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[1]
NOTICE_PATH = ROOT / "docs" / "licenses-model-cards" / "THIRD_PARTY_NOTICES.md"
SBOM_PATH = ROOT / "docs" / "licenses-model-cards" / "THIRD_PARTY_SBOM.cdx.json"
FIRST_PARTY_PYTHON = {
    "oralsight-inference",
    "oralsight-ml",
    "oralsight-platform-api",
    "oralsight-worker",
    "oralsight-workspace",
}
LICENSE_PREFIXES = ("license", "licence", "copying", "notice")
MAX_LICENSE_BYTES = 5 * 1024 * 1024


@dataclass
class Package:
    ecosystem: str
    name: str
    version: str
    license_name: str
    author: str = ""
    homepage: str = ""
    installed: bool = True
    license_files: list[Path] = field(default_factory=list)

    @property
    def identifier(self) -> str:
        return f"{self.name}@{self.version}"

    @property
    def bom_ref(self) -> str:
        return f"{self.ecosystem}:{self.identifier}"


def _command_path(name: str) -> str:
    path = shutil.which(name)
    if path is None:
        raise RuntimeError(f"Required command is unavailable: {name}")
    return path


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sort_key(value: str) -> tuple[str, str]:
    return value.casefold(), value


def _run(command: list[str]) -> str:
    completed = subprocess.run(
        command,
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError(f"Command failed ({command[0]}): {detail}")
    return completed.stdout


def _text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        return str(value.get("name") or "").strip()
    return ""


def _legal_files(package_root: Path) -> list[Path]:
    if not package_root.is_dir():
        return []
    candidates: list[Path] = []
    for child in package_root.iterdir():
        if child.is_file() and child.name.lower().startswith(LICENSE_PREFIXES):
            candidates.append(child)
    license_dir = package_root / "licenses"
    if license_dir.is_dir():
        candidates.extend(path for path in license_dir.iterdir() if path.is_file())
    return sorted(set(candidates), key=lambda path: _sort_key(path.name))


def _pnpm_packages() -> list[Package]:
    raw = _run(
        [
            _command_path("corepack"),
            "pnpm",
            "licenses",
            "list",
            "--json",
            "--long",
        ]
    )
    grouped = json.loads(raw)
    packages: dict[tuple[str, str], Package] = {}
    for license_name, entries in grouped.items():
        for entry in entries:
            roots = [Path(path) for path in entry.get("paths", [])]
            legal_files: list[Path] = []
            for root in roots:
                legal_files.extend(_legal_files(root))
            for version in entry.get("versions", []):
                key = (str(entry["name"]), str(version))
                package = packages.get(key)
                if package is None:
                    package = Package(
                        ecosystem="npm",
                        name=key[0],
                        version=key[1],
                        license_name=str(license_name),
                        author=_text(entry.get("author")),
                        homepage=_text(entry.get("homepage")),
                    )
                    packages[key] = package
                package.license_files = sorted(
                    set([*package.license_files, *legal_files]),
                    key=lambda path: _sort_key(str(path)),
                )
    return sorted(packages.values(), key=lambda item: _sort_key(item.identifier))


def _canonical_name(value: str) -> str:
    return value.casefold().replace("_", "-").replace(".", "-")


def _python_distributions() -> dict[tuple[str, str], importlib.metadata.Distribution]:
    distributions: dict[tuple[str, str], importlib.metadata.Distribution] = {}
    for distribution in importlib.metadata.distributions():
        name = distribution.metadata.get("Name")
        if not name:
            continue
        distributions[(_canonical_name(name), distribution.version)] = distribution
    return distributions


def _license_from_metadata(distribution: importlib.metadata.Distribution) -> str:
    expression = distribution.metadata.get("License-Expression")
    if expression:
        return expression.strip()
    legacy = distribution.metadata.get("License")
    if legacy and legacy.strip().casefold() not in {"unknown", "none"}:
        return legacy.strip()
    mappings = {
        "Apache Software License": "Apache-2.0",
        "BSD License": "BSD",
        "GNU General Public License v2 or later (GPLv2+)": "GPL-2.0-or-later",
        "GNU Lesser General Public License v3 or later (LGPLv3+)": (
            "LGPL-3.0-or-later"
        ),
        "ISC License (ISCL)": "ISC",
        "MIT License": "MIT",
        "Mozilla Public License 2.0 (MPL 2.0)": "MPL-2.0",
        "Python Software Foundation License": "PSF-2.0",
    }
    classifiers = distribution.metadata.get_all("Classifier") or []
    licenses = [
        mappings.get(classifier.rsplit(" :: ", 1)[-1])
        for classifier in classifiers
        if classifier.startswith("License ::")
    ]
    return " OR ".join(sorted({item for item in licenses if item})) or "UNKNOWN"


def _python_legal_files(
    distribution: importlib.metadata.Distribution,
) -> list[Path]:
    candidates: set[Path] = set()
    for relative in distribution.files or []:
        if relative.name.casefold().startswith(LICENSE_PREFIXES):
            path = Path(distribution.locate_file(relative))
            if path.is_file():
                candidates.add(path)
    dist_info = Path(distribution._path)  # type: ignore[attr-defined]
    candidates.update(_legal_files(dist_info))
    return sorted(candidates, key=lambda path: _sort_key(str(path)))


def _locked_python_bom() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="oralsight-sbom-") as directory:
        target = Path(directory) / "python.cdx.json"
        _run(
            [
                _command_path("uv"),
                "export",
                "--frozen",
                "--all-packages",
                "--all-extras",
                "--all-groups",
                "--format",
                "cyclonedx1.5",
                "--output-file",
                str(target),
                "--quiet",
            ]
        )
        return json.loads(target.read_text(encoding="utf-8"))


def _python_packages(
    locked_bom: dict[str, Any],
) -> tuple[list[Package], list[dict[str, Any]]]:
    installed = _python_distributions()
    packages: list[Package] = []
    bom_components: list[dict[str, Any]] = []
    for component in locked_bom.get("components", []):
        name = str(component.get("name") or "")
        version = str(component.get("version") or "")
        if not name or not version or name in FIRST_PARTY_PYTHON:
            continue
        distribution = installed.get((_canonical_name(name), version))
        if distribution is None:
            license_name = "NOT-IN-RELEASE-ENVIRONMENT"
            legal_files: list[Path] = []
            author = ""
            homepage = ""
        else:
            license_name = _license_from_metadata(distribution)
            legal_files = _python_legal_files(distribution)
            author = distribution.metadata.get("Author") or ""
            homepage = distribution.metadata.get("Home-page") or ""
            if not homepage:
                project_urls = distribution.metadata.get_all("Project-URL") or []
                if project_urls:
                    homepage = project_urls[0].split(",", 1)[-1].strip()
        package = Package(
            ecosystem="pypi",
            name=name,
            version=version,
            license_name=license_name,
            author=author.strip(),
            homepage=homepage.strip(),
            installed=distribution is not None,
            license_files=legal_files,
        )
        packages.append(package)
        bom_components.append(_bom_component(package))
    return (
        sorted(packages, key=lambda item: _sort_key(item.identifier)),
        sorted(bom_components, key=lambda item: _sort_key(item["bom-ref"])),
    )


def _bom_component(package: Package) -> dict[str, Any]:
    namespace = "npm" if package.ecosystem == "npm" else "pypi"
    encoded_name = quote(package.name, safe="/")
    component: dict[str, Any] = {
        "bom-ref": package.bom_ref,
        "name": package.name,
        "purl": f"pkg:{namespace}/{encoded_name}@{package.version}",
        "type": "library",
        "version": package.version,
        "licenses": [{"license": {"name": package.license_name}}],
        "properties": [
            {"name": "oralsight:ecosystem", "value": package.ecosystem},
            {
                "name": "oralsight:present-in-release-environment",
                "value": str(package.installed).lower(),
            },
        ],
    }
    if package.author:
        component["author"] = package.author
    if package.homepage:
        component["externalReferences"] = [{"type": "website", "url": package.homepage}]
    return component


def _read_legal_text(path: Path) -> str | None:
    try:
        if path.stat().st_size > MAX_LICENSE_BYTES:
            return None
        raw = path.read_bytes()
    except OSError:
        return None
    if b"\x00" in raw:
        return None
    return raw.decode("utf-8", errors="replace").replace("\r\n", "\n").strip()


def _legal_texts(packages: list[Package]) -> list[dict[str, Any]]:
    texts: dict[str, dict[str, Any]] = {}
    for package in packages:
        for path in package.license_files:
            content = _read_legal_text(path)
            if not content:
                continue
            digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
            record = texts.setdefault(
                digest,
                {"content": content, "files": set(), "packages": set()},
            )
            record["files"].add(path.name)
            record["packages"].add(f"{package.ecosystem}:{package.identifier}")
    return [
        {
            "sha256": digest,
            "content": record["content"],
            "files": sorted(record["files"], key=_sort_key),
            "packages": sorted(record["packages"], key=_sort_key),
        }
        for digest, record in sorted(texts.items())
    ]


def _escape_table(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ").strip()


def _notice_markdown(
    npm_packages: list[Package],
    python_packages: list[Package],
    legal_texts: list[dict[str, Any]],
) -> str:
    unavailable = [package for package in python_packages if not package.installed]
    pnpm_lock_sha = _sha256_file(ROOT / "pnpm-lock.yaml")
    uv_lock_sha = _sha256_file(ROOT / "uv.lock")
    lines = [
        "# Third-party dependency notices",
        "",
        "Generated from `pnpm-lock.yaml` and `uv.lock` by",
        "`scripts/generate_third_party_notices.py`. Do not edit this file by hand.",
        "This inventory is not legal advice and does not license OralSight itself.",
        "The source license and the redistribution rights for the released research",
        "model remain separate owner/legal decisions.",
        "",
        "## Inventory summary",
        "",
        f"- npm packages: {len(npm_packages)}",
        f"- locked third-party Python packages: {len(python_packages)}",
        f"- exact installed license/notice texts: {len(legal_texts)}",
        f"- locked optional Python packages absent on this platform: {len(unavailable)}",
        "- machine-readable inventory: `THIRD_PARTY_SBOM.cdx.json`",
        f"- `pnpm-lock.yaml` SHA-256: `{pnpm_lock_sha}`",
        f"- `uv.lock` SHA-256: `{uv_lock_sha}`",
        "",
        "Packages marked `NOT-IN-RELEASE-ENVIRONMENT` are retained in the uv lock",
        "for another platform or optional research extra, but were not installed or",
        "shipped by this release environment. Their terms must be reviewed before use.",
        "",
        "## npm dependency inventory",
        "",
        "| Package | Version | Declared license | Author | Homepage |",
        "| --- | --- | --- | --- | --- |",
    ]
    for package in npm_packages:
        lines.append(
            "| "
            + " | ".join(
                _escape_table(value)
                for value in (
                    package.name,
                    package.version,
                    package.license_name,
                    package.author,
                    package.homepage,
                )
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Python dependency inventory",
            "",
            "| Package | Version | Declared license | Installed here | Author | Homepage |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for package in python_packages:
        lines.append(
            "| "
            + " | ".join(
                _escape_table(value)
                for value in (
                    package.name,
                    package.version,
                    package.license_name,
                    "yes" if package.installed else "no",
                    package.author,
                    package.homepage,
                )
            )
            + " |"
        )
    lines.extend(["", "## Exact installed license and notice texts", ""])
    for index, record in enumerate(legal_texts, start=1):
        package_list = ", ".join(record["packages"])
        file_list = ", ".join(record["files"])
        lines.extend(
            [
                f"### Notice {index}",
                "",
                f"Packages: {package_list}",
                "",
                f"Source filenames: {file_list}",
                "",
                f"SHA-256: `{record['sha256']}`",
                "",
                "```text",
                record["content"],
                "```",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _generate() -> tuple[str, str]:
    npm_packages = _pnpm_packages()
    locked_python = _locked_python_bom()
    python_packages, python_components = _python_packages(locked_python)
    npm_components = [_bom_component(package) for package in npm_packages]
    components = sorted(
        [*npm_components, *python_components],
        key=lambda component: _sort_key(component["bom-ref"]),
    )
    root_ref = "application:oralsight-source"
    pnpm_lock_sha = _sha256_file(ROOT / "pnpm-lock.yaml")
    uv_lock_sha = _sha256_file(ROOT / "uv.lock")
    sbom = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "version": 1,
        "metadata": {
            "component": {
                "bom-ref": root_ref,
                "name": "OralSight source release",
                "type": "application",
                "version": "0.1.0",
            },
            "tools": {
                "components": [
                    {
                        "name": "generate_third_party_notices.py",
                        "type": "application",
                        "version": "1",
                    }
                ]
            },
            "properties": [
                {
                    "name": "oralsight:pnpm-lock-sha256",
                    "value": pnpm_lock_sha,
                },
                {"name": "oralsight:uv-lock-sha256", "value": uv_lock_sha},
            ],
        },
        "components": components,
        "dependencies": [
            {"ref": root_ref, "dependsOn": [item["bom-ref"] for item in components]}
        ],
    }
    legal_texts = _legal_texts([*npm_packages, *python_packages])
    notice = _notice_markdown(npm_packages, python_packages, legal_texts)
    sbom_text = json.dumps(sbom, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    return notice, sbom_text


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check", action="store_true", help="fail if checked artifacts are stale"
    )
    args = parser.parse_args()
    notice, sbom = _generate()
    expected = {NOTICE_PATH: notice, SBOM_PATH: sbom}
    if args.check:
        stale = [
            path
            for path, content in expected.items()
            if not path.is_file() or path.read_text(encoding="utf-8") != content
        ]
        if stale:
            print(
                "Stale third-party artifacts: " + ", ".join(str(path) for path in stale)
            )
            return 1
        print("Third-party notices and SBOM are current.")
        return 0
    for path, content in expected.items():
        path.write_text(content, encoding="utf-8", newline="\n")
        print(f"Generated {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

import tomllib
from pathlib import Path

from oralsight_api.deployment import packaged_release_manifest


def test_vercel_runtime_uses_uvicorn_without_websocket_extras() -> None:
    service_root = Path(__file__).resolve().parents[1]
    project = tomllib.loads(
        (service_root / "pyproject.toml").read_text(encoding="utf-8")
    )

    runtime_dependencies = project["project"]["dependencies"]

    assert "uvicorn==0.51.0" in runtime_dependencies
    assert not any(
        "uvicorn[" in dependency.lower() for dependency in runtime_dependencies
    )
    assert any(
        dependency.lower().startswith("uvicorn")
        for dependency in project["project"]["optional-dependencies"]["dev"]
    )


def test_vercel_entrypoint_prefers_private_release_bundle(tmp_path: Path) -> None:
    public_manifest = tmp_path / "release" / "release-manifest.json"
    private_manifest = tmp_path / "private-release" / "release-manifest.json"
    public_manifest.parent.mkdir()
    private_manifest.parent.mkdir()
    public_manifest.write_text("{}", encoding="utf-8")
    private_manifest.write_text("{}", encoding="utf-8")

    assert packaged_release_manifest(tmp_path) == private_manifest


def test_vercel_entrypoint_falls_back_to_public_release_manifest(
    tmp_path: Path,
) -> None:
    public_manifest = tmp_path / "release" / "release-manifest.json"
    public_manifest.parent.mkdir()
    public_manifest.write_text("{}", encoding="utf-8")

    assert packaged_release_manifest(tmp_path) == public_manifest

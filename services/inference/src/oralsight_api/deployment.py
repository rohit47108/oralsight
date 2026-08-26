"""Deployment-time helpers shared by local and hosted entry points."""

from pathlib import Path


def packaged_release_manifest(service_directory: Path) -> Path | None:
    """Prefer a locally supplied private bundle, then the public manifest."""

    candidates = (
        service_directory / "private-release" / "release-manifest.json",
        service_directory / "release" / "release-manifest.json",
    )
    return next((candidate for candidate in candidates if candidate.is_file()), None)

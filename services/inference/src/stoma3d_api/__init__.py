"""Stoma3D's stateless inference API."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .main import app as app

__all__ = ["app"]


def __getattr__(name: str) -> Any:
    """Load the ASGI application only when callers request it directly."""

    if name == "app":
        from .main import app

        return app
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

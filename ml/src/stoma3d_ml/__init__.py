"""Research-only ML tooling for Stoma3D.

This package does not diagnose disease and does not ship trained medical models.
"""

from .constants import MOUTH_REGIONS, THRESHOLD_VERSION

__all__ = ["MOUTH_REGIONS", "THRESHOLD_VERSION"]
__version__ = "0.1.0"

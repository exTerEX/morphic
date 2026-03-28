"""
Conversion-specific constants: which formats can be converted to which.

Uses the shared extension sets from :mod:`morphic.shared.constants` and
builds canonical conversion mapping tables.
"""

from __future__ import annotations

from morphic.shared.constants import (
    ALIASES,
    IMAGE_EXTENSIONS,
    VIDEO_EXTENSIONS,
)

# ── Canonical (de-aliased) sets ────────────────────────────────────────────
# Only the "primary" extension for each format.

_CANONICAL_IMAGE: set[str] = {
    ".jpg",
    ".png",
    ".tif",
    ".bmp",
    ".webp",
    ".gif",
    ".ico",
    ".heic",
    ".heif",
    ".avif",
}

_CANONICAL_VIDEO: set[str] = {
    ".mp4",
    ".mov",
    ".avi",
    ".mkv",
    ".webm",
    ".flv",
    ".wmv",
    ".m4v",
    ".mpeg",
    ".3gp",
    ".ts",
}


def _normalise(ext: str) -> str:
    """Resolve aliases (e.g. .jpeg -> .jpg)."""
    return ALIASES.get(ext.lower(), ext.lower())


# ── Conversion mappings ───────────────────────────────────────────────────
# source ext -> list of compatible target extensions

# Only generate mappings for extensions that have a canonical form we can
# actually write to.  Raw/vector/exotic formats are read-only.

_CONVERTIBLE_IMAGE: set[str] = {
    ext for ext in IMAGE_EXTENSIONS if _normalise(ext) in _CANONICAL_IMAGE
}

_CONVERTIBLE_VIDEO: set[str] = {
    ext for ext in VIDEO_EXTENSIONS if _normalise(ext) in _CANONICAL_VIDEO
}

IMAGE_CONVERSIONS: dict[str, list[str]] = {
    ext: sorted(_CANONICAL_IMAGE - {_normalise(ext)})
    for ext in _CONVERTIBLE_IMAGE
}

VIDEO_CONVERSIONS: dict[str, list[str]] = {
    ext: sorted(_CANONICAL_VIDEO - {_normalise(ext)})
    for ext in _CONVERTIBLE_VIDEO
}

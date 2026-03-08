"""
EXIF metadata operations — read, edit, and strip.

Uses piexif for read/write and Pillow's ExifTags for human-readable
tag name mapping.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import piexif
from PIL import Image
from PIL.ExifTags import GPSTAGS, TAGS

logger = logging.getLogger(__name__)

# ── Tag name mapping ───────────────────────────────────────────────────────

# Build reverse lookup: human name → (ifd_name, tag_id)
_NAME_TO_TAG: dict[str, tuple[str, int]] = {}
_IFD_KEYS = {
    "0th": piexif.ImageIFD,
    "Exif": piexif.ExifIFD,
    "GPS": piexif.GPSIFD,
    "1st": piexif.ImageIFD,
}

for _ifd_name, _ifd_module in [
    ("0th", piexif.ImageIFD),
    ("Exif", piexif.ExifIFD),
    ("GPS", piexif.GPSIFD),
]:
    for _attr in dir(_ifd_module):
        if _attr.startswith("_"):
            continue
        _tag_id = getattr(_ifd_module, _attr)
        if isinstance(_tag_id, int):
            _human = TAGS.get(_tag_id, _attr)
            _NAME_TO_TAG[_human] = (_ifd_name, _tag_id)


def _decode_value(value: Any) -> Any:
    """Decode piexif byte values to strings where possible."""
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8").rstrip("\x00")
        except (UnicodeDecodeError, AttributeError):
            return value.hex()
    if isinstance(value, tuple) and len(value) == 2:
        # Rational number (numerator, denominator)
        num, den = value
        if isinstance(num, int) and isinstance(den, int) and den != 0:
            return round(num / den, 6)
    return value


def _gps_to_decimal(
    coords: tuple[tuple[int, int], ...],
    ref: str,
) -> float:
    """Convert GPS DMS (degrees/minutes/seconds) to decimal degrees."""
    degrees = coords[0][0] / coords[0][1] if coords[0][1] else 0
    minutes = coords[1][0] / coords[1][1] if coords[1][1] else 0
    seconds = coords[2][0] / coords[2][1] if coords[2][1] else 0
    decimal = degrees + minutes / 60 + seconds / 3600
    if ref in ("S", "W"):
        decimal = -decimal
    return round(decimal, 6)


# ── Public API ─────────────────────────────────────────────────────────────


def read_exif(path: str) -> dict[str, Any]:
    """Read EXIF metadata from an image file.

    Parameters
    ----------
    path : str
        Path to the image file.

    Returns
    -------
    dict
        Flat dictionary of human-readable tag names to values.
        Includes ``_gps_lat`` and ``_gps_lng`` if GPS data is present.
    """
    if not os.path.isfile(path):
        raise FileNotFoundError(f"File not found: {path}")

    try:
        exif_dict = piexif.load(path)
    except piexif.InvalidImageDataError:
        # File exists but has no EXIF
        return {}
    except Exception:
        # Try via Pillow as fallback
        try:
            img = Image.open(path)
            exif_bytes = img.info.get("exif", b"")
            if not exif_bytes:
                return {}
            exif_dict = piexif.load(exif_bytes)
        except Exception:
            return {}

    result: dict[str, Any] = {}

    for ifd_name in ("0th", "Exif", "1st"):
        ifd_data = exif_dict.get(ifd_name, {})
        if not ifd_data:
            continue
        for tag_id, value in ifd_data.items():
            tag_name = TAGS.get(tag_id, f"Tag_{tag_id}")
            result[tag_name] = _decode_value(value)

    # GPS data — special handling for lat/lng
    gps_data = exif_dict.get("GPS", {})
    if gps_data:
        for tag_id, value in gps_data.items():
            tag_name = GPSTAGS.get(tag_id, f"GPSTag_{tag_id}")
            result[tag_name] = _decode_value(value)

        # Compute decimal coordinates
        lat_data = gps_data.get(piexif.GPSIFD.GPSLatitude)
        lat_ref = gps_data.get(piexif.GPSIFD.GPSLatitudeRef, b"N")
        lng_data = gps_data.get(piexif.GPSIFD.GPSLongitude)
        lng_ref = gps_data.get(piexif.GPSIFD.GPSLongitudeRef, b"E")

        if lat_data and lng_data:
            if isinstance(lat_ref, bytes):
                lat_ref = lat_ref.decode()
            if isinstance(lng_ref, bytes):
                lng_ref = lng_ref.decode()
            result["_gps_lat"] = _gps_to_decimal(lat_data, lat_ref)
            result["_gps_lng"] = _gps_to_decimal(lng_data, lng_ref)

    return result


def edit_exif(path: str, updates: dict[str, Any]) -> None:
    """Edit EXIF fields on an image file in-place.

    Parameters
    ----------
    path : str
        Path to the image file.
    updates : dict
        Mapping of human-readable tag names to new values.
        Example: ``{"Artist": "Alice", "Copyright": "2026"}``
    """
    if not os.path.isfile(path):
        raise FileNotFoundError(f"File not found: {path}")

    try:
        exif_dict = piexif.load(path)
    except Exception:
        # Start with empty EXIF
        exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}}

    for name, value in updates.items():
        tag_info = _NAME_TO_TAG.get(name)
        if not tag_info:
            logger.warning("Unknown EXIF tag name: %s", name)
            continue

        ifd_name, tag_id = tag_info
        # Encode string values to bytes
        if isinstance(value, str):
            value = value.encode("utf-8")

        if ifd_name not in exif_dict or exif_dict[ifd_name] is None:
            exif_dict[ifd_name] = {}
        exif_dict[ifd_name][tag_id] = value

    exif_bytes = piexif.dump(exif_dict)
    piexif.insert(exif_bytes, path)


def strip_exif(path: str) -> None:
    """Remove all EXIF metadata from an image file.

    Parameters
    ----------
    path : str
        Path to the image file.
    """
    if not os.path.isfile(path):
        raise FileNotFoundError(f"File not found: {path}")

    piexif.remove(path)


def strip_exif_batch(
    paths: list[str],
) -> dict[str, dict[str, str | bool]]:
    """Strip EXIF from multiple files.

    Parameters
    ----------
    paths : list[str]
        List of image file paths.

    Returns
    -------
    dict
        Per-file results: ``{"path": {"success": True/False, "error": ...}}``
    """
    results: dict[str, dict[str, str | bool]] = {}
    for path in paths:
        try:
            strip_exif(path)
            results[path] = {"success": True}
        except Exception as e:
            results[path] = {"success": False, "error": str(e)}
    return results

"""
Date-based file sorting with configurable folder templates.

Supports EXIF date extraction with fallback to file modification time,
configurable folder structure templates, and move/copy operations.
"""

from __future__ import annotations

import logging
import os
import shutil
from datetime import datetime
from pathlib import Path

import piexif

from morphic.shared.constants import ALL_EXTENSIONS
from morphic.shared.utils import find_files_by_extension

logger = logging.getLogger(__name__)

# ── Date Extraction ────────────────────────────────────────────────────────


def get_file_date(path: str) -> datetime:
    """Extract the best available date for a file.

    Priority: EXIF DateTimeOriginal → EXIF DateTime → file mtime.

    Parameters
    ----------
    path : str
        Path to the file.

    Returns
    -------
    datetime
        The extracted date.
    """
    # Try EXIF first (images only)
    try:
        exif_dict = piexif.load(path)
        for ifd_key in ("Exif", "0th"):
            ifd = exif_dict.get(ifd_key, {})
            if not ifd:
                continue
            # DateTimeOriginal = 36867, DateTime = 306
            for tag_id in (36867, 306):
                val = ifd.get(tag_id)
                if val:
                    if isinstance(val, bytes):
                        val = val.decode("utf-8", errors="ignore")
                    val = val.strip().rstrip("\x00")
                    if val and val != "0000:00:00 00:00:00":
                        return datetime.strptime(
                            val, "%Y:%m:%d %H:%M:%S",
                        )
    except Exception:
        pass

    # Fall back to file modification time
    mtime = os.path.getmtime(path)
    return datetime.fromtimestamp(mtime)


# ── Template Rendering ─────────────────────────────────────────────────────


def _render_template(template: str, dt: datetime) -> str:
    """Expand a folder template with date tokens.

    Supported tokens: ``{year}``, ``{month}``, ``{day}``,
    ``{hour}``, ``{minute}``.
    """
    return template.format(
        year=dt.strftime("%Y"),
        month=dt.strftime("%m"),
        day=dt.strftime("%d"),
        hour=dt.strftime("%H"),
        minute=dt.strftime("%M"),
    )


# ── Plan & Execute ─────────────────────────────────────────────────────────


def plan_sort(
    folder: str,
    template: str = "{year}/{month}/{day}",
    destination: str | None = None,
) -> list[dict]:
    """Generate a sort plan without executing it.

    Parameters
    ----------
    folder : str
        Source folder to scan.
    template : str
        Folder template using ``{year}``, ``{month}``, ``{day}``,
        ``{hour}``, ``{minute}`` tokens.
    destination : str, optional
        Base destination folder. Defaults to *folder* itself.

    Returns
    -------
    list[dict]
        List of ``{"source", "destination", "date", "date_formatted"}``
        entries.
    """
    base = destination or folder
    paths = find_files_by_extension(folder, ALL_EXTENSIONS)
    plan: list[dict] = []

    for path in paths:
        dt = get_file_date(path)
        sub_path = _render_template(template, dt)
        dest_dir = os.path.join(base, sub_path)
        dest_file = os.path.join(dest_dir, os.path.basename(path))

        plan.append({
            "source": path,
            "destination": dest_file,
            "date": dt.isoformat(),
            "date_formatted": dt.strftime("%Y-%m-%d %H:%M:%S"),
        })

    return plan


def execute_sort(
    plan: list[dict],
    operation: str = "copy",
) -> dict:
    """Execute a previously generated sort plan.

    Parameters
    ----------
    plan : list[dict]
        Plan from :func:`plan_sort`.
    operation : str
        ``"move"`` or ``"copy"``.

    Returns
    -------
    dict
        ``{"completed", "errors", "total", "results"}``
    """
    if operation not in ("move", "copy"):
        raise ValueError("operation must be 'move' or 'copy'")

    results: list[dict] = []
    completed = 0
    errors = 0

    for entry in plan:
        src = entry["source"]
        dest = entry["destination"]
        try:
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            if operation == "move":
                shutil.move(src, dest)
            else:
                shutil.copy2(src, dest)
            completed += 1
            results.append({
                "source": src,
                "destination": dest,
                "status": "ok",
            })
        except Exception as e:
            errors += 1
            results.append({
                "source": src,
                "destination": dest,
                "status": "error",
                "error": str(e),
            })

    return {
        "completed": completed,
        "errors": errors,
        "total": len(plan),
        "results": results,
    }

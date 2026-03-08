"""
Folder scanner – walks directories and inventories image/video files
for the format converter.
"""

from __future__ import annotations

import os
from pathlib import Path

from morphic.converter.constants import IMAGE_CONVERSIONS, VIDEO_CONVERSIONS
from morphic.shared.constants import IMAGE_EXTENSIONS, VIDEO_EXTENSIONS
from morphic.shared.utils import normalise_ext


def get_compatible_targets(source_path: str) -> list[str]:
    """Return list of extensions the source can be converted to."""
    ext = normalise_ext(Path(source_path).suffix)
    if ext in IMAGE_CONVERSIONS:
        return IMAGE_CONVERSIONS[ext]
    if ext in VIDEO_CONVERSIONS:
        return VIDEO_CONVERSIONS[ext]
    return []


def scan_folder(
    folder: str,
    include_subfolders: bool = True,
    filter_type: str = "both",
) -> dict:
    """
    Walk *folder* and return a summary + full file list.

    Parameters
    ----------
    folder : str
        Absolute path to the directory to scan.
    include_subfolders : bool
        Whether to recurse into subdirectories.
    filter_type : str
        One of ``"images"``, ``"videos"``, ``"both"``.

    Returns
    -------
    dict
        ``{"folder", "summary", "files", "total"}``
    """
    allowed: set[str] = set()
    if filter_type in ("images", "both"):
        allowed |= IMAGE_EXTENSIONS
    if filter_type in ("videos", "both"):
        allowed |= VIDEO_EXTENSIONS

    summary: dict[str, int] = {}
    files: list[dict] = []

    if include_subfolders:
        walker = os.walk(folder)
    else:
        try:
            entries = os.listdir(folder)
        except PermissionError:
            entries = []
        walker = [(folder, [], entries)]  # type: ignore[assignment]

    for dirpath, _dirs, filenames in walker:
        for fname in filenames:
            full = os.path.join(dirpath, fname)
            ext = normalise_ext(Path(fname).suffix)
            if ext not in allowed:
                continue
            try:
                size = os.path.getsize(full)
            except OSError:
                size = 0

            ftype = "image" if ext in IMAGE_EXTENSIONS else "video"
            targets = get_compatible_targets(full)

            summary[ext] = summary.get(ext, 0) + 1
            files.append({
                "path": full,
                "name": fname,
                "ext": ext,
                "size": size,
                "type": ftype,
                "targets": targets,
            })

    sorted_summary = dict(sorted(summary.items(), key=lambda x: -x[1]))

    return {
        "folder": folder,
        "summary": sorted_summary,
        "files": sorted(files, key=lambda f: f["name"].lower()),
        "total": len(files),
    }

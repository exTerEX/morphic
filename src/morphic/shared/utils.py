"""
Shared utility helpers used across morphic modules.
"""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Generator


from morphic.shared.constants import (
    ALIASES,
    EXCLUDED_FOLDERS,
    IMAGE_EXTENSIONS,
    VIDEO_EXTENSIONS,
)

logger = logging.getLogger(__name__)


# ── Extension helpers ──────────────────────────────────────────────────────


def normalise_ext(ext: str) -> str:
    """Lowercase and unify aliases (.jpeg -> .jpg, .tiff -> .tif)."""
    ext = ext.lower()
    return ALIASES.get(ext, ext)


def is_image(path: str) -> bool:
    """Return True if the file extension is an image type."""
    return normalise_ext(Path(path).suffix) in IMAGE_EXTENSIONS


def is_video(path: str) -> bool:
    """Return True if the file extension is a video type."""
    return normalise_ext(Path(path).suffix) in VIDEO_EXTENSIONS


# ── Formatting helpers ─────────────────────────────────────────────────────


def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format."""
    size = float(size_bytes)
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} TB"


def format_duration(seconds: float) -> str:
    """Format duration in human-readable format."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    if hours > 0:
        return f"{hours}h {minutes}m {secs}s"
    if minutes > 0:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


# ── File scanning helpers ──────────────────────────────────────────────────


def is_excluded_path(
    file_path: str,
    excluded_folders: frozenset[str] = EXCLUDED_FOLDERS,
) -> bool:
    """Check if a file path contains any excluded folder."""
    path_parts = Path(file_path).parts
    return any(
        excluded in part.lower()
        for part in path_parts
        for excluded in excluded_folders
    )


def find_files_by_extension(
    folder: str,
    extensions: frozenset[str] | set[str],
    excluded_folders: frozenset[str] = EXCLUDED_FOLDERS,
) -> list[str]:
    """
    Find all files with given extensions in *folder* recursively.

    Parameters
    ----------
    folder : str
        Root folder to search.
    extensions : set[str]
        File extensions to match (with dot, e.g. ``".jpg"``).
    excluded_folders : set[str]
        Folder names to exclude.

    Returns
    -------
    list[str]
        Sorted list of absolute file paths.
    """
    files: list[str] = []
    folder_path = Path(folder)
    logger.info("Scanning for files in: %s", folder)

    for ext in extensions:
        files.extend(str(p) for p in folder_path.rglob(f"*{ext}"))
        files.extend(str(p) for p in folder_path.rglob(f"*{ext.upper()}"))

    # De-duplicate and filter
    files = sorted(
        {f for f in files if not is_excluded_path(f, excluded_folders)}
    )
    logger.info("Found %d files", len(files))
    return files


# ── stderr suppression (for OpenCV/ffmpeg) ─────────────────────────────────


@contextmanager
def suppress_stderr() -> Generator[None, None, None]:
    """
    Suppress stderr output at the file-descriptor level.

    Silences low-level library warnings (e.g. ffmpeg/OpenCV codec messages)
    that cannot be caught by Python's logging framework.
    """
    devnull_fd = os.open(os.devnull, os.O_WRONLY)
    old_stderr_fd = os.dup(2)
    os.dup2(devnull_fd, 2)
    try:
        yield
    finally:
        os.dup2(old_stderr_fd, 2)
        os.close(devnull_fd)
        os.close(old_stderr_fd)

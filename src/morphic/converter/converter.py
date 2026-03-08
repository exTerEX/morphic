"""
File conversion engine – Pillow for images, ffmpeg for videos.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from PIL import Image

from morphic.shared.utils import is_image, is_video, normalise_ext


def _ffmpeg_available() -> bool:
    """Return True if ffmpeg is on PATH."""
    return shutil.which("ffmpeg") is not None


def convert_image(
    source: str,
    target_ext: str,
    output_dir: str | None = None,
) -> str:
    """
    Convert an image file using Pillow.

    Parameters
    ----------
    source : str
        Path to the source image.
    target_ext : str
        Target extension (with or without leading dot).
    output_dir : str, optional
        Directory for the output file.  Defaults to the source directory.

    Returns
    -------
    str
        Path of the converted file.
    """
    src = Path(source)
    target_ext = target_ext if target_ext.startswith(".") else f".{target_ext}"
    target_ext = normalise_ext(target_ext)

    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        dest = Path(output_dir) / (src.stem + target_ext)
    else:
        dest = src.with_suffix(target_ext)

    # Avoid overwriting existing files
    if dest.exists():
        dest = dest.with_stem(dest.stem + "_converted")

    img = Image.open(source)

    # Handle RGBA -> formats that don't support alpha
    if img.mode == "RGBA" and target_ext in {".jpg", ".jpeg", ".bmp", ".ico"}:
        img = img.convert("RGB")
    elif img.mode == "P" and target_ext in {".jpg", ".jpeg"}:
        img = img.convert("RGB")

    save_kwargs: dict = {}
    if target_ext in {".jpg", ".jpeg"}:
        save_kwargs["quality"] = 95
    elif target_ext == ".webp":
        save_kwargs["quality"] = 90
    elif target_ext in {".tif", ".tiff"}:
        save_kwargs["compression"] = "tiff_lzw"

    img.save(str(dest), **save_kwargs)
    return str(dest)


def convert_video(
    source: str,
    target_ext: str,
    output_dir: str | None = None,
) -> str:
    """
    Convert a video file using ffmpeg.

    Parameters
    ----------
    source : str
        Path to the source video.
    target_ext : str
        Target extension (with or without leading dot).
    output_dir : str, optional
        Directory for the output file.  Defaults to the source directory.

    Returns
    -------
    str
        Path of the converted file.

    Raises
    ------
    RuntimeError
        If ffmpeg is not installed or conversion fails.
    """
    if not _ffmpeg_available():
        raise RuntimeError(
            "ffmpeg is not installed or not on PATH. "
            "Install it: https://ffmpeg.org/download.html"
        )

    src = Path(source)
    target_ext = target_ext if target_ext.startswith(".") else f".{target_ext}"
    target_ext = normalise_ext(target_ext)

    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        dest = Path(output_dir) / (src.stem + target_ext)
    else:
        dest = src.with_suffix(target_ext)

    if dest.exists():
        dest = dest.with_stem(dest.stem + "_converted")

    # Use stream-copy for container-only conversions
    if target_ext in {".mkv", ".ts"}:
        cmd = [
            "ffmpeg", "-y", "-i", str(src),
            "-c", "copy",
            str(dest),
        ]
    else:
        cmd = [
            "ffmpeg", "-y", "-i", str(src),
            "-c:v", "libx264", "-c:a", "aac",
            "-preset", "fast", "-crf", "23",
            str(dest),
        ]

    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=600,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg error: {result.stderr[:500]}")

    return str(dest)


def convert_file(
    source: str,
    target_ext: str,
    output_dir: str | None = None,
) -> str:
    """High-level converter – routes to image or video handler."""
    if is_image(source):
        return convert_image(source, target_ext, output_dir)
    if is_video(source):
        return convert_video(source, target_ext, output_dir)
    raise ValueError(f"Unsupported file type: {source}")

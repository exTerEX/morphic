"""
Thumbnail generation shared by converter and dupfinder frontends.

Generates JPEG thumbnails for images (Pillow) and videos (ffmpeg subprocess).
"""

from __future__ import annotations

import io
import logging
import subprocess

from PIL import Image

logger = logging.getLogger(__name__)


def generate_image_thumbnail(
    file_path: str,
    size: int = 300,
) -> io.BytesIO:
    """
    Create a JPEG thumbnail for an image file.

    Parameters
    ----------
    file_path : str
        Absolute path to the image.
    size : int
        Maximum width/height in pixels.

    Returns
    -------
    io.BytesIO
        JPEG image bytes (seeked to 0).
    """
    img = Image.open(file_path)
    img.thumbnail((size, size), Image.Resampling.LANCZOS)

    if img.mode in ("RGBA", "P", "LA"):
        img = img.convert("RGB")

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80)
    buf.seek(0)
    return buf


def generate_video_thumbnail(
    file_path: str,
    size: int = 300,
) -> io.BytesIO | None:
    """
    Extract a single frame from a video and return it as a JPEG thumbnail.

    Uses ``ffmpeg`` piped to stdout.  Returns ``None`` on failure.

    Parameters
    ----------
    file_path : str
        Absolute path to the video.
    size : int
        Maximum width/height in pixels.

    Returns
    -------
    io.BytesIO | None
        JPEG image bytes (seeked to 0), or ``None``.
    """
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        file_path,
        "-ss",
        "00:00:01",
        "-vframes",
        "1",
        "-vf",
        (f"scale={size}:{size}:force_original_aspect_ratio=decrease"),
        "-f",
        "image2pipe",
        "-vcodec",
        "mjpeg",
        "-q:v",
        "5",
        "pipe:1",
    ]
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=10,
    )
    if result.returncode != 0 or not result.stdout:
        # Retry at 0s for very short clips
        cmd[5] = "00:00:00"
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
        )
    if result.stdout:
        buf = io.BytesIO(result.stdout)
        return buf
    return None

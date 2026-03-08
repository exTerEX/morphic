"""
File integrity checking for images and videos.

Uses Pillow's ``verify()`` / ``load()`` for images and ``ffprobe``
for videos.
"""

from __future__ import annotations

import logging
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed

from PIL import Image

from morphic.shared.constants import IMAGE_EXTENSIONS, VIDEO_EXTENSIONS
from morphic.shared.utils import (
    find_files_by_extension,
    format_file_size,
    is_image,
    is_video,
)

logger = logging.getLogger(__name__)


def check_image(path: str) -> dict:
    """Validate an image file's integrity.

    Parameters
    ----------
    path : str
        Path to the image file.

    Returns
    -------
    dict
        ``{"path", "valid", "error", "size", "size_formatted",
        "width", "height", "format"}``
    """
    result: dict = {
        "path": path,
        "valid": False,
        "error": None,
        "size": 0,
        "size_formatted": "0 B",
        "width": 0,
        "height": 0,
        "format": None,
        "type": "image",
    }

    if not os.path.isfile(path):
        result["error"] = "File not found"
        return result

    result["size"] = os.path.getsize(path)
    result["size_formatted"] = format_file_size(result["size"])

    if result["size"] == 0:
        result["error"] = "Zero-byte file"
        return result

    try:
        # First pass: verify structure
        img = Image.open(path)
        result["format"] = img.format
        result["width"] = img.width
        result["height"] = img.height
        img.verify()

        # Second pass: actually decode all pixels
        img = Image.open(path)
        img.load()

        result["valid"] = True
    except Exception as e:
        result["error"] = str(e)

    return result


def check_video(path: str) -> dict:
    """Validate a video file using ffprobe.

    Parameters
    ----------
    path : str
        Path to the video file.

    Returns
    -------
    dict
        ``{"path", "valid", "error", "size", "size_formatted",
        "width", "height", "duration", "codec"}``
    """
    result: dict = {
        "path": path,
        "valid": False,
        "error": None,
        "size": 0,
        "size_formatted": "0 B",
        "width": 0,
        "height": 0,
        "duration": 0.0,
        "codec": None,
        "type": "video",
    }

    if not os.path.isfile(path):
        result["error"] = "File not found"
        return result

    result["size"] = os.path.getsize(path)
    result["size_formatted"] = format_file_size(result["size"])

    if result["size"] == 0:
        result["error"] = "Zero-byte file"
        return result

    try:
        cmd = [
            "ffprobe",
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries",
            "stream=codec_name,width,height,duration",
            "-of", "csv=p=0",
            path,
        ]
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if proc.returncode != 0:
            stderr = proc.stderr.strip()
            result["error"] = stderr or f"ffprobe exit code {proc.returncode}"
            return result

        output = proc.stdout.strip()
        if not output:
            result["error"] = "No video stream found"
            return result

        parts = output.split(",")
        if len(parts) >= 1:
            result["codec"] = parts[0]
        if len(parts) >= 2:
            result["width"] = int(parts[1]) if parts[1] else 0
        if len(parts) >= 3:
            result["height"] = int(parts[2]) if parts[2] else 0
        if len(parts) >= 4 and parts[3]:
            try:
                result["duration"] = float(parts[3])
            except ValueError:
                pass

        result["valid"] = True

    except FileNotFoundError:
        result["error"] = "ffprobe not found (install ffmpeg)"
    except subprocess.TimeoutExpired:
        result["error"] = "ffprobe timed out"
    except Exception as e:
        result["error"] = str(e)

    return result


def check_files(
    folder: str,
    max_workers: int = 4,
) -> list[dict]:
    """Check integrity of all media files in a folder.

    Parameters
    ----------
    folder : str
        Root folder to scan.
    max_workers : int
        Number of threads for parallel checking.

    Returns
    -------
    list[dict]
        Per-file integrity results.
    """
    all_ext = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS
    paths = find_files_by_extension(folder, all_ext)
    results: list[dict] = []

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {}
        for path in paths:
            if is_image(path):
                futures[pool.submit(check_image, path)] = path
            elif is_video(path):
                futures[pool.submit(check_video, path)] = path

        for future in as_completed(futures):
            try:
                results.append(future.result())
            except Exception as e:
                results.append({
                    "path": futures[future],
                    "valid": False,
                    "error": str(e),
                })

    return sorted(results, key=lambda r: r["path"])

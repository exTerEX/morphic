"""
File conversion engine – Pillow for images, ffmpeg for videos.
"""

from __future__ import annotations

import importlib
import os
import shutil
import subprocess
from pathlib import Path

from PIL import Image

from morphic.shared.utils import is_image, is_video, normalise_ext


def _ffmpeg_available() -> bool:
    """Return True if ffmpeg is on PATH."""
    return shutil.which("ffmpeg") is not None


def _is_torch_cuda_available() -> bool:
    """Return True if torch is installed and CUDA is available."""
    try:
        torch = importlib.import_module("torch")

        return torch.cuda.is_available()
    except Exception:
        return False


def _ffmpeg_has_encoder(encoder: str) -> bool:
    """Check if ffmpeg has a particular video encoder available."""
    try:
        output = subprocess.check_output(
            ["ffmpeg", "-hide_banner", "-encoders"],
            stderr=subprocess.STDOUT,
            text=True,
            timeout=15,
        )
        return any(encoder in line for line in output.splitlines())
    except Exception:
        return False


def _ffmpeg_has_hwaccel(hwaccel: str) -> bool:
    """Check if ffmpeg supports a particular hardware acceleration method."""
    try:
        output = subprocess.check_output(
            ["ffmpeg", "-hide_banner", "-hwaccels"],
            stderr=subprocess.STDOUT,
            text=True,
            timeout=15,
        )
        return any(hwaccel in line for line in output.splitlines())
    except Exception:
        return False


def _get_video_encoder(target_ext: str) -> tuple[str, bool, str]:
    """Select a video encoder (and whether to request hardware acceleration).

    Returns (encoder, use_hwaccel, output_extension).
    """
    ext = target_ext.lower().lstrip(".")
    output_ext = ext

    if ext.endswith("-av1"):
        output_ext = ext.split("-")[0]
        # For AV1 try available encoders in preferred order.
        use_cuda = _is_torch_cuda_available() and _ffmpeg_has_hwaccel("cuda")
        if use_cuda and _ffmpeg_has_encoder("av1_nvenc"):
            return "av1_nvenc", True, output_ext
        if _ffmpeg_has_encoder("libsvtav1"):
            return "libsvtav1", False, output_ext
        if _ffmpeg_has_encoder("libaom-av1"):
            return "libaom-av1", False, output_ext
        if _ffmpeg_has_encoder("libvpx-vp9"):
            # VP9 older fallback if AV1 is unavailable
            return "libvpx-vp9", False, output_ext
        # fall back to H.264 if no AV1 encoder installed
        return "libx264", False, output_ext

    # Prefer NVIDIA nvenc if available for standard containers.
    use_cuda = _is_torch_cuda_available() and _ffmpeg_has_hwaccel("cuda")
    if output_ext in ("mp4", "mkv", "mov") and use_cuda:
        if _ffmpeg_has_encoder("h264_nvenc"):
            return "h264_nvenc", True, output_ext
        if _ffmpeg_has_encoder("hevc_nvenc"):
            return "hevc_nvenc", True, output_ext
    # fallback to GPU-like to ensure we do not use missing nvenc
    if output_ext in ("mp4", "mkv", "mov"):
        return "libx264", False, output_ext
    if output_ext == "webm" and _ffmpeg_has_encoder("vp9_nvenc"):
        return "vp9_nvenc", True, output_ext

    # Fallback to software encoders.
    if output_ext in ("mp4", "mkv", "mov"):
        return "libx264", False, output_ext
    if output_ext == "webm":
        return "libvpx-vp9", False, output_ext
    if output_ext == "avi":
        return "mpeg4", False, output_ext
    if output_ext in ("flv", "mpeg", "3gp", "ts"):
        return "libx264", False, output_ext

    # Generic fallback
    return "libx264", False, output_ext


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
    av1_crf: int | None = None,
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

    codec_target_ext = target_ext
    if (
        target_ext.startswith(".mp4-av1")
        or target_ext.startswith(".mkv-av1")
        or target_ext.startswith(".webm-av1")
    ):
        # select container from it, preserve compatible extension
        container_ext = target_ext.split("-", 1)[0]
        codec_target_ext = container_ext
    else:
        codec_target_ext = target_ext

    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        dest = Path(output_dir) / (src.stem + codec_target_ext)
    else:
        dest = src.with_suffix(codec_target_ext)

    if dest.exists():
        dest = dest.with_stem(dest.stem + "_converted")

    # Use stream-copy for container-only conversions
    if codec_target_ext in {".mkv", ".ts"}:
        cmd = ["ffmpeg", "-y", "-i", str(src), "-c", "copy", str(dest)]
    else:
        encoder, hwaccel, _out_ext = _get_video_encoder(target_ext)
        cmd = ["ffmpeg", "-y"]

        if hwaccel and _ffmpeg_has_hwaccel("cuda"):
            cmd += ["-hwaccel", "cuda"]

        audio_codec = "aac"
        if codec_target_ext == ".avi":
            # AVI prefers mp3 audio or PCM
            audio_codec = "libmp3lame"

        if codec_target_ext == ".webm" and encoder in (
            "libx264",
            "h264_nvenc",
            "h264",
        ):
            # WebM should use VP9/AV1; keep default
            pass

        cmd += ["-i", str(src), "-c:v", encoder, "-c:a", audio_codec]

        if encoder.endswith("nvenc"):
            cmd += ["-preset", "fast", "-rc", "vbr", "-cq", "23"]
        else:
            if encoder in ("libaom-av1", "libsvtav1", "av1_nvenc"):
                # AV1 quality presets and CRF management
                av1_default_crf = (
                    32 if encoder in ("libaom-av1", "av1_nvenc") else 28
                )
                if av1_crf is not None and 10 <= av1_crf <= 63:
                    chosen_crf = av1_crf
                else:
                    chosen_crf = av1_default_crf
                cmd += ["-preset", "fast", "-crf", str(chosen_crf)]
            else:
                cmd += ["-preset", "fast", "-crf", "23"]

        cmd.append(str(dest))

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=600,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"ffmpeg error (code {result.returncode}): {result.stderr.strip()}"
        )

    return str(dest)


def convert_file(
    source: str,
    target_ext: str,
    output_dir: str | None = None,
    av1_crf: int | None = None,
) -> str:
    """High-level converter – routes to image or video handler."""
    if is_image(source):
        return convert_image(source, target_ext, output_dir)
    if is_video(source):
        return convert_video(source, target_ext, output_dir, av1_crf=av1_crf)
    raise ValueError(f"Unsupported file type: {source}")

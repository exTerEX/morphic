"""
Image resize operations — fit, fill, stretch, and pad.

All operations preserve the original format by default and support
configurable output quality and format override.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from PIL import Image, ImageOps

logger = logging.getLogger(__name__)

# Valid resize modes
RESIZE_MODES = ("fit", "fill", "stretch", "pad")


def resize_image(
    path: str,
    width: int,
    height: int,
    mode: str = "fit",
    output_folder: str | None = None,
    bg_color: str = "#000000",
    quality: int = 90,
    output_format: str | None = None,
) -> str:
    """Resize a single image.

    Parameters
    ----------
    path : str
        Path to the source image.
    width : int
        Target width in pixels.
    height : int
        Target height in pixels.
    mode : str
        Resize mode: ``"fit"`` (within bounds), ``"fill"`` (cover + crop),
        ``"stretch"`` (ignore ratio), ``"pad"`` (fit + pad borders).
    output_folder : str, optional
        Write output here instead of overwriting. Creates the folder
        if needed.
    bg_color : str
        Background colour for pad mode (CSS hex, default black).
    quality : int
        JPEG/WebP quality (1-100).
    output_format : str, optional
        Force output format (e.g. ``".png"``). Uses original if *None*.

    Returns
    -------
    str
        Path to the output file.

    Raises
    ------
    FileNotFoundError
        If the source file does not exist.
    ValueError
        If an invalid mode is given.
    """
    if not os.path.isfile(path):
        raise FileNotFoundError(f"File not found: {path}")
    if mode not in RESIZE_MODES:
        raise ValueError(
            f"Invalid mode '{mode}'. Must be one of {RESIZE_MODES}"
        )
    if width <= 0 or height <= 0:
        raise ValueError("Width and height must be positive integers")

    img = Image.open(path)

    # Convert palette/LA images to RGBA/RGB for processing
    if img.mode in ("P", "LA"):
        img = img.convert("RGBA")
    elif img.mode == "L":
        img = img.convert("RGB")

    size = (width, height)

    if mode == "fit":
        img.thumbnail(size, Image.Resampling.LANCZOS)
    elif mode == "fill":
        img = ImageOps.fit(img, size, Image.Resampling.LANCZOS)
    elif mode == "stretch":
        img = img.resize(size, Image.Resampling.LANCZOS)
    elif mode == "pad":
        img = ImageOps.pad(img, size, Image.Resampling.LANCZOS, color=bg_color)

    # Determine output path
    src = Path(path)
    ext = output_format if output_format else src.suffix
    if not ext.startswith("."):
        ext = f".{ext}"

    if output_folder:
        os.makedirs(output_folder, exist_ok=True)
        dest = Path(output_folder) / f"{src.stem}{ext}"
    else:
        dest = src.with_suffix(ext)

    # Convert RGBA to RGB for formats that don't support alpha
    if img.mode == "RGBA" and ext.lower() in (".jpg", ".jpeg", ".bmp"):
        img = img.convert("RGB")

    save_kwargs: dict = {}
    if ext.lower() in (".jpg", ".jpeg", ".webp"):
        save_kwargs["quality"] = quality
    if ext.lower() == ".png":
        save_kwargs["optimize"] = True

    img.save(str(dest), **save_kwargs)
    logger.info("Resized %s → %s (%s)", path, dest, mode)
    return str(dest)

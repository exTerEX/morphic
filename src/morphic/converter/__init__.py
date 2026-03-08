"""
morphic.converter - File format conversion engine.

Provides image conversion (Pillow) and video conversion (ffmpeg).
"""

from morphic.converter.constants import (
    IMAGE_CONVERSIONS,
    VIDEO_CONVERSIONS,
)
from morphic.converter.converter import (
    convert_file,
    convert_image,
    convert_video,
)
from morphic.converter.scanner import scan_folder

__all__ = [
    "IMAGE_CONVERSIONS",
    "VIDEO_CONVERSIONS",
    "convert_file",
    "convert_image",
    "convert_video",
    "scan_folder",
]

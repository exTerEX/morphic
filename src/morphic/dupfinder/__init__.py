"""
morphic.dupfinder - Duplicate image/video detection via perceptual hashing.

Ported from the standalone dupfinder project, now sharing constants and
utilities with the rest of morphic.
"""

from morphic.dupfinder.images import (
    ImageDuplicateFinder,
    ImageHasher,
    ImageInfo,
)
from morphic.dupfinder.videos import (
    VideoDuplicateFinder,
    VideoHasher,
    VideoInfo,
)
from morphic.dupfinder.accelerator import (
    AcceleratorType,
    GPUAccelerator,
    get_accelerator,
)

__all__ = [
    "AcceleratorType",
    "GPUAccelerator",
    "ImageDuplicateFinder",
    "ImageHasher",
    "ImageInfo",
    "VideoDuplicateFinder",
    "VideoHasher",
    "VideoInfo",
    "get_accelerator",
]

"""
morphic.resizer - Batch image resizing with multiple modes.

Supports fit, fill, stretch, and pad operations with configurable
output format and background colour.
"""

from morphic.resizer.operations import resize_image
from morphic.resizer.scanner import get_job, start_job

__all__ = [
    "get_job",
    "resize_image",
    "start_job",
]

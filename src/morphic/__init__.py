"""
morphic - Unified media toolkit: format conversion and duplicate detection.

This package provides:

- **morphic.converter** - Scan folders and batch-convert images/videos
- **morphic.dupfinder** - Find duplicate images/videos via perceptual hashing
- **morphic.frontend** - Shared Flask web UI with tabbed interface

Quick start::

    # Launch the web UI
    morphic

    # With options
    morphic --port 9000 --folder /path/to/media
"""

from importlib.metadata import metadata as _metadata

_meta = _metadata(__name__)
__version__ = _meta["Version"]
__author__ = _meta["Author"]

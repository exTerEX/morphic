"""
morphic.frontend — Unified web interface for all morphic modules.

Usage::

    morphic
    python -m morphic.frontend
"""

from morphic.frontend.app import create_app, main

__all__ = [
    "create_app",
    "main",
]

Changelog
=========

1.0.0 (2026-03-06)
-------------------

Initial public release.

- Unified media toolkit: format conversion and duplicate detection in a
  single tabbed web UI
- **Converter** — scan folders and batch-convert image/video files;
  22 image formats (Pillow) and 21 video formats (ffmpeg)
- **Dupfinder** — find visually similar images and videos using
  perceptual hashing; GPU acceleration via CUDA, ROCm, and OpenCL
- **Shared UI** — tabbed Flask web interface with in-page folder
  browser, thumbnail preview, and dark theme
- Native folder-picker dialogs (tkinter / zenity / kdialog / osascript /
  PowerShell) with in-page fallback
- GPU-accelerated batch processing (CUDA/PyTorch, CuPy, OpenCL)
- ``morphic`` CLI with ``--host``, ``--port``, ``--folder``,
  ``--debug``, and ``--no-browser`` options
- Sphinx documentation published to GitHub Pages
- Comprehensive test suite with 94 %+ code coverage

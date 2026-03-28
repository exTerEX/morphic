# morphic

Unified media toolkit — format conversion, duplicate detection, EXIF inspection, batch resizing, and file organization in a single tabbed web UI.

## Features

### Converter
- **Folder scanning** — enter any path, toggle subfolder recursion, filter by images / videos / both
- **File summary** — colour-coded bar chart and badge counts per extension
- **Batch conversion** — select files, pick a target format, convert in one click
- **Live progress** — real-time progress bar with per-file success / error feedback
- **Image formats** — jpg, png, tif, bmp, webp, gif, ico, heic, heif, avif (via Pillow)
- **Video formats** — mp4, mov, avi, mkv, webm, flv, wmv, m4v, mpeg, 3gp, ts (via ffmpeg)

### Dupfinder
- **Perceptual hashing** — find visually similar images and videos, not just exact matches
- **GPU acceleration** — CUDA (PyTorch/CuPy), ROCm, OpenCL, with CPU fallback
- **Video analysis** — extract and hash frames to detect duplicate video content
- **Batch processing** — process thousands of files with configurable thresholds
- **Space savings** — see how much disk space you'd recover by removing duplicates

### Inspector
- **EXIF metadata** — read, edit, and strip EXIF tags from images (via piexif)
- **Integrity checking** — validate images (Pillow verify + load) and videos (ffprobe)
- **Background scanning** — scan entire folders with progress tracking
- **GPS decoding** — automatic DMS-to-decimal coordinate conversion

### Resizer
- **Batch resize** — resize images in bulk with configurable dimensions
- **Four modes** — fit (contain), fill (cover + crop), stretch (exact), pad (letterbox)
- **Quality control** — configurable JPEG/WebP quality and background color for padding
- **Format override** — optionally convert output format during resize

### Organizer
- **Date sorting** — sort files into date-based folder structures (EXIF → mtime fallback)
- **Batch renaming** — rename files with template tokens ({date}, {seq}, {original}, {ext})
- **Plan & execute** — preview the plan before committing (move or copy)
- **Conflict detection** — automatically detects and skips naming conflicts

### Shared
- **Native folder browser** — OS-native file dialog (tkinter, zenity, kdialog, etc.)
- **Thumbnail generation** — image and video thumbnails in the web UI
- **Dark theme** — clean, responsive interface

## Quick Start

```bash
# Install and launch
uv sync
morphic
```

The browser opens automatically at **http://127.0.0.1:8000**.

```bash
# With options
morphic --port 9000 --folder ~/Pictures --no-browser
```

## Prerequisites

- **Python ≥ 3.10**
- **[uv](https://docs.astral.sh/uv/)** — fast Python package manager
- **ffmpeg** (optional) — required for video conversion

```bash
# Ubuntu / Debian
sudo apt install ffmpeg
```

### Optional Extras

```bash
uv sync --extra gpu     # NVIDIA CUDA via PyTorch + CuPy
uv sync --extra heif    # HEIF/HEIC support via pillow-heif
```

> GPU environment requirements
> - Use Python 3.10-3.13 for the torchvision/CuPy stack (PyTorch 1.13.x + CuPy 13.x).
> - Set up a dedicated venv with `python3.11 -m venv .venv` and activate it before running `uv sync --extra gpu`.
> - On Python 3.14 the recommended GPU extras are skipped because PyTorch/CuPy wheels are not yet published for that interpreter in this branch.

> GPU note for GTX 10-series (sm_61):
> - This repository uses `torch` from the optional `gpu` group.
> - For NVIDIA GeForce GTX 1070, install torch 1.13.x (CUDA 11.6/11.7) in a Python 3.11 environment
>   (`torch>=1.13.1,<2.0.0`), because newer PyTorch binary builds drop support for sm_61.
> - Example:
>   `pip install torch==1.13.1+cu116 torchvision==0.14.1+cu116 -f https://download.pytorch.org/whl/torch_stable.html`
> - Then `uv sync --extra gpu` can resolve `cupy` and `pyopencl` components normally.

## Development

```bash
make install    # Install all dependencies
make test       # Run tests
make coverage   # Run with coverage report (94%+)
make lint       # Lint (ruff + pyright)
make format     # Auto-format
make docs       # Build Sphinx documentation
make clean      # Remove build artifacts
```

## Documentation

Build and view the full documentation:

```bash
make docs
open docs/_build/html/index.html
```

## License

MIT

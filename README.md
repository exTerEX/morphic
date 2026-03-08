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
# macOS
brew install ffmpeg
```

### Optional Extras

```bash
uv sync --extra gpu     # NVIDIA CUDA via PyTorch + CuPy
uv sync --extra heif    # HEIF/HEIC support via pillow-heif
```

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

## Project Structure

```
morphic/
├── src/morphic/
│   ├── __init__.py              # Package root, version
│   ├── shared/                  # Constants, utils, thumbnails, file browser
│   ├── converter/               # Format conversion engine
│   ├── dupfinder/               # Duplicate detection
│   ├── inspector/               # EXIF metadata & file integrity
│   │   ├── exif.py
│   │   ├── integrity.py
│   │   └── scanner.py
│   ├── resizer/                 # Batch image resizing
│   │   ├── operations.py
│   │   └── scanner.py
│   ├── organizer/               # Date sorting & batch renaming
│   │   ├── date_sorter.py
│   │   ├── renamer.py
│   │   └── scanner.py
│   └── frontend/                # Flask web UI
│       ├── app.py
│       ├── routes_shared.py
│       ├── routes_converter.py
│       ├── routes_dupfinder.py
│       ├── routes_inspector.py
│       ├── routes_resizer.py
│       ├── routes_organizer.py
│       ├── templates/
│       └── static/
├── tests/                       # 430+ tests
│   ├── shared/
│   ├── converter/
│   ├── dupfinder/
│   ├── inspector/
│   ├── resizer/
│   ├── organizer/
│   └── frontend/
├── docs/                        # Sphinx documentation (furo theme)
├── pyproject.toml
├── Makefile
└── README.md
```

## Documentation

Build and view the full documentation:

```bash
make docs
open docs/_build/html/index.html
```

## License

MIT

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
# Build and run with Makefile targets
git clone <repo>
cd morphic
make go-build
./bin/morphic                      # starts server at http://127.0.0.1:8000
```

```bash
# With options
./bin/morphic --port 9000 --folder ~/Pictures --no-browser
```

## Prerequisites

- Go 1.22+
- ffmpeg (optional) — required for video conversion

```bash
# Ubuntu / Debian
sudo apt install ffmpeg
```

## Development

```bash
make go-tidy     # sync go.mod/go.sum
make go-test     # run unit tests
make go-vet      # static vet checks
make go-build    # build binary in ./bin/morphic
make go-run      # build + run dev server
```

## License

This project is released under the MIT License and is free to use, modify, and distribute.

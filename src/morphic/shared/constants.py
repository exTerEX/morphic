"""
Shared constants for morphic – extension sets, exclusion lists, defaults.

Merges constants from both the converter and dupfinder modules so that
every part of the project works with a single canonical set of
supported file types.
"""

from __future__ import annotations

# ── Supported extensions ───────────────────────────────────────────────────
# Union of converter + dupfinder sets.

IMAGE_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".jpg",
        ".jpeg",
        ".png",
        ".tif",
        ".tiff",
        ".bmp",
        ".webp",
        ".gif",
        ".ico",
        ".heic",
        ".heif",
        ".avif",
        # Extra formats from dupfinder (raw / vector)
        ".svg",
        ".raw",
        ".cr2",
        ".nef",
        ".arw",
        ".dng",
        ".orf",
        ".rw2",
        ".pef",
        ".srw",
    }
)

VIDEO_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".mp4",
        ".mov",
        ".avi",
        ".mkv",
        ".webm",
        ".flv",
        ".wmv",
        ".m4v",
        ".mpeg",
        ".mpg",
        ".3gp",
        ".ts",
        # Extra formats from dupfinder
        ".ogv",
        ".mts",
        ".m2ts",
        ".vob",
        ".divx",
        ".xvid",
        ".asf",
        ".rm",
        ".rmvb",
    }
)

ALL_EXTENSIONS: frozenset[str] = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS

# ── Folders to skip when scanning ──────────────────────────────────────────

EXCLUDED_FOLDERS: frozenset[str] = frozenset(
    {
        # Windows
        "$recycle.bin",
        "$recycle",
        "recycler",
        "recycled",
        "system volume information",
        "windows",
        "appdata",
        # macOS
        ".trash",
        ".trashes",
        ".spotlight-v100",
        ".fseventsd",
        ".ds_store",
        # Linux
        "lost+found",
        "trash",
        # Thumbnails
        ".thumbnails",
        ".thumb",
        "thumbs",
        # NAS
        "@eadir",
        # Version control
        ".git",
        ".svn",
        ".hg",
        # Development
        "__pycache__",
        ".cache",
        "node_modules",
        ".venv",
        "venv",
    }
)

# ── Alias resolution ──────────────────────────────────────────────────────

ALIASES: dict[str, str] = {
    ".jpeg": ".jpg",
    ".tiff": ".tif",
    ".mpg": ".mpeg",
}

# ── Dupfinder default thresholds ──────────────────────────────────────────

DEFAULT_IMAGE_THRESHOLD: float = 0.90
DEFAULT_VIDEO_THRESHOLD: float = 0.85
DEFAULT_HASH_SIZE: int = 16
DEFAULT_NUM_FRAMES: int = 10
DEFAULT_NUM_WORKERS: int = 4
DEFAULT_BATCH_SIZE: int = 1000

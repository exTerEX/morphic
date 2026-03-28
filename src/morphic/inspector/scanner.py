"""
Background scan job management for the inspector module.

Handles EXIF scanning and integrity checking in background threads.
"""

from __future__ import annotations

import logging
import os
import threading
import time
import uuid
from dataclasses import dataclass, field

from morphic.shared.constants import ALL_EXTENSIONS, IMAGE_EXTENSIONS
from morphic.shared.utils import (
    find_files_by_extension,
    format_duration,
    is_image,
    is_video,
)

logger = logging.getLogger(__name__)


@dataclass
class ScanJob:
    """Represents a running or completed inspector job."""

    id: str
    folder: str
    mode: str  # "exif" or "integrity"
    status: str = "pending"
    progress: float = 0.0
    message: str = ""
    error: str | None = None
    results: list[dict] = field(default_factory=list)
    total_files: int = 0
    processed_files: int = 0
    started_at: float = 0.0
    finished_at: float = 0.0


# ── Job Registry ───────────────────────────────────────────────────────────

_jobs: dict[str, ScanJob] = {}
_lock = threading.Lock()


def get_job(job_id: str) -> ScanJob | None:
    """Retrieve a scan job by ID."""
    with _lock:
        return _jobs.get(job_id)


def start_job(folder: str, mode: str) -> str:
    """Create and launch a new inspector job. Returns the job ID."""
    job_id = str(uuid.uuid4())[:8]
    job = ScanJob(id=job_id, folder=folder, mode=mode)
    with _lock:
        _jobs[job_id] = job

    thread = threading.Thread(target=_run_scan, args=(job,), daemon=True)
    thread.start()
    return job_id


def _run_scan(job: ScanJob) -> None:
    """Execute the inspector scan in a background thread."""
    try:
        job.status = "scanning"
        job.started_at = time.time()

        # Determine extensions to look for
        extensions = IMAGE_EXTENSIONS if job.mode == "exif" else ALL_EXTENSIONS
        job.message = f"Scanning folder: {job.folder}"
        paths = find_files_by_extension(job.folder, extensions)
        job.total_files = len(paths)

        if not paths:
            job.status = "done"
            job.progress = 1.0
            job.finished_at = time.time()
            job.message = "No files found."
            return

        job.status = "processing"

        if job.mode == "exif":
            _scan_exif(job, paths)
        else:
            _scan_integrity(job, paths)

        job.status = "done"
        job.progress = 1.0
        job.finished_at = time.time()
        elapsed = job.finished_at - job.started_at
        job.message = (
            f"Done! Processed {job.processed_files} files "
            f"in {format_duration(elapsed)}."
        )

    except Exception as e:
        logger.exception("Inspector scan failed")
        job.status = "error"
        job.error = str(e)
        job.message = f"Error: {e}"
        job.finished_at = time.time()


def _scan_exif(job: ScanJob, paths: list[str]) -> None:
    """Read EXIF from all image files."""
    from morphic.inspector.exif import read_exif

    for i, path in enumerate(paths):
        if not is_image(path):
            continue
        try:
            exif = read_exif(path)
            job.results.append(
                {
                    "path": path,
                    "filename": os.path.basename(path),
                    "directory": os.path.dirname(path),
                    "exif": exif,
                    "has_exif": bool(exif),
                    "has_gps": "_gps_lat" in exif,
                }
            )
        except Exception as e:
            job.results.append(
                {
                    "path": path,
                    "filename": os.path.basename(path),
                    "directory": os.path.dirname(path),
                    "exif": {},
                    "has_exif": False,
                    "has_gps": False,
                    "error": str(e),
                }
            )
        job.processed_files = i + 1
        job.progress = (i + 1) / job.total_files
        job.message = f"Reading EXIF: {i + 1}/{job.total_files}"


def _scan_integrity(job: ScanJob, paths: list[str]) -> None:
    """Check integrity of all media files."""
    from morphic.inspector.integrity import check_image, check_video

    for i, path in enumerate(paths):
        if is_image(path):
            result = check_image(path)
        elif is_video(path):
            result = check_video(path)
        else:
            result = {
                "path": path,
                "valid": False,
                "error": "Unknown file type",
                "type": "unknown",
            }
        result["filename"] = os.path.basename(path)
        result["directory"] = os.path.dirname(path)
        job.results.append(result)
        job.processed_files = i + 1
        job.progress = (i + 1) / job.total_files
        job.message = f"Checking: {i + 1}/{job.total_files}"

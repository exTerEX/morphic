"""
Background scan job management for the resizer module.

Discovers images in a folder and resizes them in a background thread.
"""

from __future__ import annotations

import logging
import os
import threading
import time
import uuid
from dataclasses import dataclass, field

from morphic.shared.constants import IMAGE_EXTENSIONS
from morphic.shared.utils import (
    find_files_by_extension,
    format_duration,
    format_file_size,
)

logger = logging.getLogger(__name__)


@dataclass
class ScanJob:
    """Represents a running or completed resize job."""

    id: str
    folder: str
    width: int
    height: int
    mode: str
    output_folder: str | None = None
    bg_color: str = "#000000"
    quality: int = 90
    status: str = "pending"
    progress: float = 0.0
    message: str = ""
    error: str | None = None
    total_files: int = 0
    processed_files: int = 0
    errors: list[dict] = field(default_factory=list)
    results: list[dict] = field(default_factory=list)
    started_at: float = 0.0
    finished_at: float = 0.0


# ── Job Registry ───────────────────────────────────────────────────────────

_jobs: dict[str, ScanJob] = {}
_lock = threading.Lock()


def get_job(job_id: str) -> ScanJob | None:
    """Retrieve a resize job by ID."""
    with _lock:
        return _jobs.get(job_id)


def start_job(
    folder: str,
    width: int,
    height: int,
    mode: str,
    output_folder: str | None = None,
    bg_color: str = "#000000",
    quality: int = 90,
) -> str:
    """Create and launch a new resize job. Returns the job ID."""
    job_id = str(uuid.uuid4())[:8]
    job = ScanJob(
        id=job_id,
        folder=folder,
        width=width,
        height=height,
        mode=mode,
        output_folder=output_folder,
        bg_color=bg_color,
        quality=quality,
    )
    with _lock:
        _jobs[job_id] = job

    thread = threading.Thread(target=_run_resize, args=(job,), daemon=True)
    thread.start()
    return job_id


def _run_resize(job: ScanJob) -> None:
    """Execute the resize operation in a background thread."""
    from morphic.resizer.operations import resize_image

    try:
        job.status = "scanning"
        job.started_at = time.time()
        job.message = f"Scanning folder: {job.folder}"

        paths = find_files_by_extension(job.folder, IMAGE_EXTENSIONS)
        job.total_files = len(paths)

        if not paths:
            job.status = "done"
            job.progress = 1.0
            job.finished_at = time.time()
            job.message = "No image files found."
            return

        job.status = "processing"
        for i, path in enumerate(paths):
            try:
                original_size = os.path.getsize(path)
                dest = resize_image(
                    path,
                    job.width,
                    job.height,
                    mode=job.mode,
                    output_folder=job.output_folder,
                    bg_color=job.bg_color,
                    quality=job.quality,
                )
                new_size = os.path.getsize(dest) if os.path.isfile(dest) else 0
                job.results.append(
                    {
                        "source": path,
                        "destination": dest,
                        "status": "ok",
                        "original_size": original_size,
                        "new_size": new_size,
                        "original_size_fmt": format_file_size(original_size),
                        "new_size_fmt": format_file_size(new_size),
                    }
                )
            except Exception as e:
                job.errors.append({"path": path, "error": str(e)})
                job.results.append(
                    {
                        "source": path,
                        "destination": None,
                        "status": "error",
                        "error": str(e),
                    }
                )

            job.processed_files = i + 1
            job.progress = (i + 1) / job.total_files
            job.message = (
                f"Resizing: {i + 1}/{job.total_files} "
                f"({len(job.errors)} errors)"
            )

        job.status = "done"
        job.progress = 1.0
        job.finished_at = time.time()
        elapsed = job.finished_at - job.started_at
        job.message = (
            f"Done! Resized {job.processed_files} images "
            f"in {format_duration(elapsed)}. "
            f"{len(job.errors)} error(s)."
        )

    except Exception as e:
        logger.exception("Resize job failed")
        job.status = "error"
        job.error = str(e)
        job.message = f"Error: {e}"
        job.finished_at = time.time()

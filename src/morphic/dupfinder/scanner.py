"""
Background scan job management for the dupfinder web UI.

Handles running duplicate-detection scans in background threads and
converting results into JSON-serializable formats.
"""

from __future__ import annotations

import logging
import os
import threading
import time
import uuid
from dataclasses import dataclass, field

from morphic.shared.constants import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_HASH_SIZE,
    DEFAULT_IMAGE_THRESHOLD,
    DEFAULT_NUM_FRAMES,
    DEFAULT_NUM_WORKERS,
    DEFAULT_VIDEO_THRESHOLD,
)
from morphic.shared.utils import format_duration, format_file_size
from morphic.dupfinder.images import ImageDuplicateFinder, ImageInfo
from morphic.dupfinder.videos import VideoDuplicateFinder, VideoInfo

logger = logging.getLogger(__name__)


# ── Data Structures ────────────────────────────────────────────────────────


@dataclass
class ScanJob:
    """Represents a running or completed scan job."""

    id: str
    folder: str
    scan_type: str  # "images", "videos", "both"
    status: str = "pending"
    progress: float = 0.0
    message: str = ""
    error: str | None = None
    # Results
    image_groups: list[list[dict]] = field(default_factory=list)
    video_groups: list[list[dict]] = field(default_factory=list)
    image_infos: dict[str, ImageInfo] = field(default_factory=dict)
    video_infos: dict[str, VideoInfo] = field(default_factory=dict)
    total_files_found: int = 0
    total_files_processed: int = 0
    space_savings: int = 0
    started_at: float = 0.0
    finished_at: float = 0.0
    # Settings
    image_threshold: float = DEFAULT_IMAGE_THRESHOLD
    video_threshold: float = DEFAULT_VIDEO_THRESHOLD


# ── Job Registry ───────────────────────────────────────────────────────────

_scan_jobs: dict[str, ScanJob] = {}
_scan_lock = threading.Lock()


def get_job(job_id: str) -> ScanJob | None:
    """Retrieve a scan job by ID."""
    with _scan_lock:
        return _scan_jobs.get(job_id)


def start_job(
    folder: str,
    scan_type: str,
    image_threshold: float = DEFAULT_IMAGE_THRESHOLD,
    video_threshold: float = DEFAULT_VIDEO_THRESHOLD,
) -> str:
    """Create and launch a new scan job. Returns the job ID."""
    job_id = str(uuid.uuid4())[:8]
    job = ScanJob(
        id=job_id,
        folder=folder,
        scan_type=scan_type,
        image_threshold=image_threshold,
        video_threshold=video_threshold,
    )
    with _scan_lock:
        _scan_jobs[job_id] = job

    thread = threading.Thread(target=_run_scan, args=(job,), daemon=True)
    thread.start()
    return job_id


# ── Background Worker ──────────────────────────────────────────────────────


def _run_scan(job: ScanJob) -> None:
    """Execute the scan in a background thread."""
    try:
        job.status = "scanning"
        job.started_at = time.time()
        job.message = f"Scanning folder: {job.folder}"

        # ── Image Scan ─────────────────────────────────────────────
        if job.scan_type in ("images", "both"):
            job.message = "Finding image files..."
            finder = ImageDuplicateFinder(
                similarity_threshold=job.image_threshold,
                hash_size=DEFAULT_HASH_SIZE,
                num_workers=DEFAULT_NUM_WORKERS,
                use_gpu=True,
                batch_size=DEFAULT_BATCH_SIZE,
            )
            image_files = finder.find_images(job.folder)
            job.total_files_found += len(image_files)
            job.message = (
                f"Found {len(image_files)} images. Processing hashes..."
            )
            job.progress = 0.1

            if image_files:
                job.status = "processing"
                finder.process_images(image_files)
                job.image_infos = finder.image_infos
                job.total_files_processed += len(finder.image_infos)
                job.progress = (
                    0.4 if job.scan_type == "both" else 0.7
                )
                job.message = (
                    f"Processed {len(finder.image_infos)} images. "
                    "Finding duplicates..."
                )

                job.status = "comparing"
                groups = finder.find_duplicates()
                job.image_groups = _format_image_groups(
                    groups, finder.image_infos,
                )
                job.progress = (
                    0.5 if job.scan_type == "both" else 0.95
                )

        # ── Video Scan ─────────────────────────────────────────────
        if job.scan_type in ("videos", "both"):
            job.message = "Finding video files..."
            vfinder = VideoDuplicateFinder(
                similarity_threshold=job.video_threshold,
                num_frames=DEFAULT_NUM_FRAMES,
                hash_size=DEFAULT_HASH_SIZE,
                num_workers=DEFAULT_NUM_WORKERS,
                use_gpu=True,
            )
            video_files = vfinder.find_videos(job.folder)
            job.total_files_found += len(video_files)
            job.message = (
                f"Found {len(video_files)} videos. Processing hashes..."
            )
            job.progress = (
                0.6 if job.scan_type == "both" else 0.1
            )

            if video_files:
                job.status = "processing"
                vfinder.process_videos(video_files)
                job.video_infos = vfinder.video_infos
                job.total_files_processed += len(vfinder.video_infos)
                job.progress = (
                    0.8 if job.scan_type == "both" else 0.7
                )
                job.message = (
                    f"Processed {len(vfinder.video_infos)} videos. "
                    "Finding duplicates..."
                )

                job.status = "comparing"
                groups = vfinder.find_duplicates()
                job.video_groups = _format_video_groups(
                    groups, vfinder.video_infos,
                )
                job.progress = 0.95

        # ── Finalise ───────────────────────────────────────────────
        job.space_savings = _calculate_space_savings(job)
        job.status = "done"
        job.progress = 1.0
        job.finished_at = time.time()
        elapsed = job.finished_at - job.started_at
        total_groups = len(job.image_groups) + len(job.video_groups)
        job.message = (
            f"Done! Found {total_groups} duplicate group(s) "
            f"in {elapsed:.1f}s. "
            f"Potential savings: {format_file_size(job.space_savings)}"
        )

    except Exception as e:
        logger.exception("Scan failed")
        job.status = "error"
        job.error = str(e)
        job.message = f"Error: {e}"
        job.finished_at = time.time()


# ── Result Formatters ──────────────────────────────────────────────────────


def _format_image_groups(
    groups: list[list[tuple[str, float]]],
    infos: dict[str, ImageInfo],
) -> list[list[dict]]:
    """Convert image duplicate groups to JSON-serializable dicts."""
    result = []
    for group in groups:
        formatted = []
        sorted_group = sorted(
            group,
            key=lambda x: infos.get(
                x[0], ImageInfo(path=""),
            ).file_size,
            reverse=True,
        )
        for path, similarity in sorted_group:
            info = infos.get(path)
            if info:
                formatted.append({
                    "path": path,
                    "filename": os.path.basename(path),
                    "directory": os.path.dirname(path),
                    "width": info.width,
                    "height": info.height,
                    "resolution": f"{info.width}x{info.height}",
                    "format": info.format or "Unknown",
                    "file_size": info.file_size,
                    "file_size_formatted": format_file_size(
                        info.file_size,
                    ),
                    "similarity": round(similarity * 100, 1),
                    "type": "image",
                })
        if len(formatted) > 1:
            result.append(formatted)
    return result


def _format_video_groups(
    groups: list[list[tuple[str, float]]],
    infos: dict[str, VideoInfo],
) -> list[list[dict]]:
    """Convert video duplicate groups to JSON-serializable dicts."""
    result = []
    for group in groups:
        formatted = []
        sorted_group = sorted(
            group,
            key=lambda x: infos.get(
                x[0], VideoInfo(path=""),
            ).file_size,
            reverse=True,
        )
        for path, similarity in sorted_group:
            info = infos.get(path)
            if info:
                formatted.append({
                    "path": path,
                    "filename": os.path.basename(path),
                    "directory": os.path.dirname(path),
                    "width": info.width,
                    "height": info.height,
                    "resolution": f"{info.width}x{info.height}",
                    "duration": info.duration,
                    "duration_formatted": format_duration(
                        info.duration,
                    ),
                    "fps": round(info.fps, 1),
                    "file_size": info.file_size,
                    "file_size_formatted": format_file_size(
                        info.file_size,
                    ),
                    "similarity": round(similarity * 100, 1),
                    "type": "video",
                })
        if len(formatted) > 1:
            result.append(formatted)
    return result


def _calculate_space_savings(job: ScanJob) -> int:
    """Sum up file sizes for all but the largest file in each group."""
    total = 0
    for group in job.image_groups + job.video_groups:
        sizes = [item["file_size"] for item in group]
        if len(sizes) > 1:
            total += sum(sorted(sizes)[:-1])
    return total

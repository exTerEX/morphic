"""
Background job management for the organizer module.

Handles plan→preview→execute workflows for date sorting and batch
renaming in background threads.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field

from morphic.shared.utils import format_duration

logger = logging.getLogger(__name__)


@dataclass
class ScanJob:
    """Represents a running or completed organizer job."""

    id: str
    folder: str
    mode: str  # "sort" or "rename"
    operation: str = "copy"  # "move" or "copy"
    template: str = "{year}/{month}/{day}"
    destination: str | None = None
    start_seq: int = 1
    status: str = "pending"
    phase: str = "idle"  # "planning", "executing", "done"
    progress: float = 0.0
    message: str = ""
    error: str | None = None
    plan: list[dict] = field(default_factory=list)
    execution_result: dict = field(default_factory=dict)
    started_at: float = 0.0
    finished_at: float = 0.0


# ── Job Registry ───────────────────────────────────────────────────────────

_jobs: dict[str, ScanJob] = {}
_lock = threading.Lock()


def get_job(job_id: str) -> ScanJob | None:
    """Retrieve an organizer job by ID."""
    with _lock:
        return _jobs.get(job_id)


def start_job(
    folder: str,
    mode: str,
    operation: str = "copy",
    template: str = "{year}/{month}/{day}",
    destination: str | None = None,
    start_seq: int = 1,
) -> str:
    """Create and launch a planning job. Returns the job ID."""
    job_id = str(uuid.uuid4())[:8]
    job = ScanJob(
        id=job_id,
        folder=folder,
        mode=mode,
        operation=operation,
        template=template,
        destination=destination,
        start_seq=start_seq,
    )
    with _lock:
        _jobs[job_id] = job

    thread = threading.Thread(target=_run_plan, args=(job,), daemon=True)
    thread.start()
    return job_id


def execute_job(job_id: str) -> bool:
    """Execute a previously planned job. Returns False if not found."""
    with _lock:
        job = _jobs.get(job_id)
    if not job or job.phase != "planned":
        return False

    thread = threading.Thread(
        target=_run_execute,
        args=(job,),
        daemon=True,
    )
    thread.start()
    return True


def _run_plan(job: ScanJob) -> None:
    """Generate the plan in a background thread."""
    try:
        job.status = "scanning"
        job.phase = "planning"
        job.started_at = time.time()
        job.message = f"Planning {job.mode} for: {job.folder}"

        if job.mode == "sort":
            from morphic.organizer.date_sorter import plan_sort

            job.plan = plan_sort(
                job.folder,
                template=job.template,
                destination=job.destination,
            )
        else:
            from morphic.organizer.renamer import plan_rename

            job.plan = plan_rename(
                job.folder,
                template=job.template,
                operation=job.operation,
                start_seq=job.start_seq,
                output_folder=job.destination,
            )

        job.phase = "planned"
        job.status = "planned"
        job.progress = 0.5
        job.message = (
            f"Plan ready: {len(job.plan)} file(s) to {job.operation}."
        )

    except Exception as e:
        logger.exception("Organizer planning failed")
        job.status = "error"
        job.error = str(e)
        job.message = f"Error: {e}"
        job.finished_at = time.time()


def _run_execute(job: ScanJob) -> None:
    """Execute the plan in a background thread."""
    try:
        job.status = "processing"
        job.phase = "executing"
        job.message = f"Executing {job.operation}..."

        if job.mode == "sort":
            from morphic.organizer.date_sorter import execute_sort

            job.execution_result = execute_sort(
                job.plan,
                operation=job.operation,
            )
        else:
            from morphic.organizer.renamer import execute_rename

            job.execution_result = execute_rename(
                job.plan,
                operation=job.operation,
            )

        job.phase = "done"
        job.status = "done"
        job.progress = 1.0
        job.finished_at = time.time()
        elapsed = job.finished_at - job.started_at
        res = job.execution_result
        job.message = (
            f"Done! {res.get('completed', 0)} files "
            f"{job.operation}d, {res.get('errors', 0)} error(s) "
            f"in {format_duration(elapsed)}."
        )

    except Exception as e:
        logger.exception("Organizer execution failed")
        job.status = "error"
        job.error = str(e)
        job.message = f"Error: {e}"
        job.finished_at = time.time()

"""
Converter-tab API routes — scan, formats, convert, delete, progress.
"""

from __future__ import annotations

import os
import threading
import time
import uuid

from flask import Blueprint, jsonify, request

from morphic.converter.constants import IMAGE_CONVERSIONS, VIDEO_CONVERSIONS
from morphic.converter.converter import convert_file
from morphic.converter.scanner import scan_folder
from morphic.shared.utils import format_file_size

bp = Blueprint("converter", __name__)

# ── In-memory progress store ───────────────────────────────────────────────

_conversion_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()


# ── Scan ───────────────────────────────────────────────────────────────────


@bp.route("/scan", methods=["POST"])
def api_scan():
    """Scan a folder for convertible media files."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON body"}), 400

    folder = data.get("folder", "").strip()
    if not folder or not os.path.isdir(folder):
        return jsonify({"error": f"Invalid folder: {folder}"}), 400

    include_sub = data.get("include_subfolders", True)
    filter_type = data.get("filter_type", "both")
    if filter_type not in ("images", "videos", "both"):
        filter_type = "both"

    result = scan_folder(
        folder,
        include_subfolders=include_sub,
        filter_type=filter_type,
    )
    return jsonify(result)


# ── Formats ────────────────────────────────────────────────────────────────


@bp.route("/formats")
def api_formats():
    """Return all conversion mappings (source -> targets)."""
    return jsonify({
        "image": IMAGE_CONVERSIONS,
        "video": VIDEO_CONVERSIONS,
    })


# ── Convert ────────────────────────────────────────────────────────────────


@bp.route("/convert", methods=["POST"])
def api_convert():
    """Convert files and return progress job id."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON body"}), 400

    files = data.get("files", [])
    target_ext = data.get("target_ext", "").strip()
    delete_original = data.get("delete_original", False)

    if not files or not target_ext:
        return jsonify({"error": "files and target_ext required"}), 400

    job_id = str(uuid.uuid4())[:8]
    job = {
        "id": job_id,
        "status": "running",
        "total": len(files),
        "completed": 0,
        "current_file": "",
        "results": [],
        "error": None,
    }
    with _jobs_lock:
        _conversion_jobs[job_id] = job

    thread = threading.Thread(
        target=_run_conversion,
        args=(job, files, target_ext, delete_original),
        daemon=True,
    )
    thread.start()
    return jsonify({"job_id": job_id}), 202


def _run_conversion(
    job: dict,
    files: list[str],
    target_ext: str,
    delete_original: bool,
) -> None:
    """Background worker for batch conversion."""
    for i, source in enumerate(files):
        job["current_file"] = os.path.basename(source)
        try:
            original_size = os.path.getsize(source) if os.path.isfile(source) else 0
            dest = convert_file(source, target_ext)
            new_size = os.path.getsize(dest) if os.path.isfile(dest) else 0

            result = {
                "source": source,
                "destination": dest,
                "status": "ok",
                "original_size": original_size,
                "new_size": new_size,
                "original_size_fmt": format_file_size(original_size),
                "new_size_fmt": format_file_size(new_size),
            }

            if delete_original and os.path.isfile(source):
                try:
                    os.remove(source)
                    result["source_deleted"] = True
                except OSError:
                    result["source_deleted"] = False
        except Exception as e:
            result = {
                "source": source,
                "destination": None,
                "status": "error",
                "error": str(e),
            }
        job["results"].append(result)
        job["completed"] = i + 1

    job["status"] = "done"
    job["current_file"] = ""


# ── Progress ───────────────────────────────────────────────────────────────


@bp.route("/progress/<job_id>")
def api_progress(job_id: str):
    """Get progress of a conversion job."""
    with _jobs_lock:
        job = _conversion_jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify(job)


@bp.route("/progress/<job_id>/poll")
def api_progress_poll(job_id: str):
    """Long-poll for conversion progress (blocks up to 10s)."""
    with _jobs_lock:
        job = _conversion_jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    # Lightweight polling — wait until progress changes or timeout
    last_completed = int(request.args.get("last", -1))
    deadline = time.time() + 10
    while time.time() < deadline:
        if job["completed"] != last_completed or job["status"] == "done":
            return jsonify(job)
        time.sleep(0.3)
    return jsonify(job)


# ── Delete (standalone) ───────────────────────────────────────────────────


@bp.route("/delete", methods=["POST"])
def api_delete():
    """Delete selected files."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON body"}), 400

    files = data.get("files", [])
    if not files:
        return jsonify({"error": "No files specified"}), 400

    results = []
    total_freed = 0

    for fp in files:
        try:
            if not os.path.isfile(fp):
                results.append({"path": fp, "status": "not_found"})
                continue
            size = os.path.getsize(fp)
            os.remove(fp)
            total_freed += size
            results.append({
                "path": fp,
                "status": "deleted",
                "size_freed": size,
            })
        except PermissionError:
            results.append({"path": fp, "status": "permission_denied"})
        except Exception as e:
            results.append({"path": fp, "status": "error", "error": str(e)})

    return jsonify({
        "results": results,
        "total_freed": total_freed,
        "total_freed_formatted": format_file_size(total_freed),
    })

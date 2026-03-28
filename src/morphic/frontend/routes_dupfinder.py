"""
Dupfinder-tab API routes — scan, status, results, delete.
"""

from __future__ import annotations

import os
import time

from flask import Blueprint, jsonify, request

from morphic.shared.constants import (
    DEFAULT_IMAGE_THRESHOLD,
    DEFAULT_VIDEO_THRESHOLD,
)
from morphic.shared.utils import format_file_size
from morphic.dupfinder.scanner import get_job, start_job

bp = Blueprint("dupfinder", __name__)


# ── Scan ───────────────────────────────────────────────────────────────────


@bp.route("/scan", methods=["POST"])
def api_start_scan():
    """Start a new duplicate scan."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON body"}), 400

    folder = data.get("folder", "").strip()
    scan_type = data.get("type", "both")
    image_threshold = float(
        data.get("image_threshold", DEFAULT_IMAGE_THRESHOLD),
    )
    video_threshold = float(
        data.get("video_threshold", DEFAULT_VIDEO_THRESHOLD),
    )

    if not folder or not os.path.isdir(folder):
        return jsonify({"error": f"Invalid folder: {folder}"}), 400
    if scan_type not in ("images", "videos", "both"):
        return jsonify(
            {
                "error": "type must be images, videos, or both",
            }
        ), 400

    job_id = start_job(
        folder=folder,
        scan_type=scan_type,
        image_threshold=image_threshold,
        video_threshold=video_threshold,
    )
    return jsonify({"job_id": job_id}), 202


# ── Status & results ──────────────────────────────────────────────────────


@bp.route("/scan/<job_id>/status")
def api_scan_status(job_id: str):
    """Get status of a scan job."""
    job = get_job(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    elapsed = 0.0
    if job.started_at:
        end = job.finished_at if job.finished_at else time.time()
        elapsed = end - job.started_at

    return jsonify(
        {
            "id": job.id,
            "status": job.status,
            "progress": job.progress,
            "message": job.message,
            "error": job.error,
            "total_files_found": job.total_files_found,
            "total_files_processed": job.total_files_processed,
            "elapsed_seconds": round(elapsed, 1),
        }
    )


@bp.route("/scan/<job_id>/results")
def api_scan_results(job_id: str):
    """Get results of a completed scan."""
    job = get_job(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    if job.status not in ("done", "error"):
        return jsonify({"error": "Scan not finished yet"}), 409

    return jsonify(
        {
            "image_groups": job.image_groups,
            "video_groups": job.video_groups,
            "space_savings": job.space_savings,
            "space_savings_formatted": format_file_size(job.space_savings),
        }
    )


# ── Delete ─────────────────────────────────────────────────────────────────


@bp.route("/delete", methods=["POST"])
def api_delete_files():
    """Delete selected duplicate files."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON body"}), 400

    files = data.get("files", [])
    if not files:
        return jsonify({"error": "No files specified"}), 400

    results = []
    total_freed = 0

    for file_path in files:
        try:
            if not os.path.isfile(file_path):
                results.append({"path": file_path, "status": "not_found"})
                continue
            file_size = os.path.getsize(file_path)
            os.remove(file_path)
            total_freed += file_size
            results.append(
                {
                    "path": file_path,
                    "status": "deleted",
                    "size_freed": file_size,
                }
            )
        except PermissionError:
            results.append(
                {
                    "path": file_path,
                    "status": "permission_denied",
                }
            )
        except Exception as e:
            results.append(
                {
                    "path": file_path,
                    "status": "error",
                    "error": str(e),
                }
            )

    return jsonify(
        {
            "results": results,
            "total_freed": total_freed,
            "total_freed_formatted": format_file_size(total_freed),
        }
    )

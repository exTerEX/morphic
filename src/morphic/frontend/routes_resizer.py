"""
Resizer-tab API routes — scan, status, results.
"""

from __future__ import annotations

import os
import time

from flask import Blueprint, jsonify, request

from morphic.resizer.operations import RESIZE_MODES
from morphic.resizer.scanner import get_job, start_job

bp = Blueprint("resizer", __name__)


@bp.route("/scan", methods=["POST"])
def api_start_resize():
    """Start a batch resize job."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON body"}), 400

    folder = data.get("folder", "").strip()
    width = data.get("width", 0)
    height = data.get("height", 0)
    mode = data.get("mode", "fit")
    bg_color = data.get("bg_color", "#000000")
    quality = data.get("quality", 90)
    output_folder = data.get("output_folder", "").strip() or None

    if not folder or not os.path.isdir(folder):
        return jsonify({"error": f"Invalid folder: {folder}"}), 400

    try:
        width = int(width)
        height = int(height)
    except (TypeError, ValueError):
        return jsonify({"error": "width and height must be integers"}), 400

    if width <= 0 or height <= 0:
        return jsonify({"error": "width and height must be positive"}), 400

    if mode not in RESIZE_MODES:
        return jsonify(
            {
                "error": f"mode must be one of {RESIZE_MODES}",
            }
        ), 400

    job_id = start_job(
        folder=folder,
        width=width,
        height=height,
        mode=mode,
        output_folder=output_folder,
        bg_color=bg_color,
        quality=quality,
    )
    return jsonify({"job_id": job_id}), 202


@bp.route("/scan/<job_id>/status")
def api_scan_status(job_id: str):
    """Get status of a resize job."""
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
            "total_files": job.total_files,
            "processed_files": job.processed_files,
            "elapsed_seconds": round(elapsed, 1),
        }
    )


@bp.route("/scan/<job_id>/results")
def api_scan_results(job_id: str):
    """Get results of a completed resize job."""
    job = get_job(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    if job.status not in ("done", "error"):
        return jsonify({"error": "Job not finished yet"}), 409

    return jsonify(
        {
            "results": job.results,
            "errors": job.errors,
            "total_files": job.total_files,
            "processed_files": job.processed_files,
        }
    )

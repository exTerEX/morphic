"""
Organizer-tab API routes — plan, execute, status for sort & rename.
"""

from __future__ import annotations

import os
import time

from flask import Blueprint, jsonify, request

from morphic.organizer.scanner import execute_job, get_job, start_job

bp = Blueprint("organizer", __name__)


@bp.route("/plan", methods=["POST"])
def api_plan():
    """Create a sort/rename plan (does not execute)."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON body"}), 400

    folder = data.get("folder", "").strip()
    mode = data.get("mode", "sort")
    operation = data.get("operation", "copy")
    template = data.get("template", "{year}/{month}/{day}")
    destination = data.get("destination", "").strip() or None
    start_seq = int(data.get("start_seq", 1))

    if not folder or not os.path.isdir(folder):
        return jsonify({"error": f"Invalid folder: {folder}"}), 400
    if mode not in ("sort", "rename"):
        return jsonify({"error": "mode must be 'sort' or 'rename'"}), 400
    if operation not in ("move", "copy"):
        return jsonify({"error": "operation must be 'move' or 'copy'"}), 400

    job_id = start_job(
        folder=folder,
        mode=mode,
        operation=operation,
        template=template,
        destination=destination,
        start_seq=start_seq,
    )
    return jsonify({"job_id": job_id}), 202


@bp.route("/execute", methods=["POST"])
def api_execute():
    """Execute a previously planned job."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON body"}), 400

    job_id = data.get("job_id", "").strip()
    if not job_id:
        return jsonify({"error": "job_id required"}), 400

    ok = execute_job(job_id)
    if not ok:
        return jsonify({
            "error": "Job not found or not in 'planned' state",
        }), 404

    return jsonify({"status": "executing", "job_id": job_id}), 202


@bp.route("/status/<job_id>")
def api_status(job_id: str):
    """Get status of an organizer job."""
    job = get_job(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    elapsed = 0.0
    if job.started_at:
        end = job.finished_at if job.finished_at else time.time()
        elapsed = end - job.started_at

    response = {
        "id": job.id,
        "status": job.status,
        "phase": job.phase,
        "mode": job.mode,
        "operation": job.operation,
        "progress": job.progress,
        "message": job.message,
        "error": job.error,
        "elapsed_seconds": round(elapsed, 1),
    }

    # Include plan preview when planning is done
    if job.phase in ("planned", "executing", "done"):
        response["plan"] = job.plan
        response["plan_count"] = len(job.plan)
        conflicts = sum(1 for e in job.plan if e.get("conflict"))
        response["conflicts"] = conflicts

    # Include execution results when done
    if job.phase == "done" and job.execution_result:
        response["execution"] = job.execution_result

    return jsonify(response)

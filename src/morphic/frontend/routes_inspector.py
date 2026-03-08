"""
Inspector-tab API routes — EXIF scan, integrity check, edit, strip.
"""

from __future__ import annotations

import os
import time

from flask import Blueprint, jsonify, request

from morphic.inspector.scanner import get_job, start_job

bp = Blueprint("inspector", __name__)


# ── Scan (EXIF or Integrity) ──────────────────────────────────────────────


@bp.route("/scan", methods=["POST"])
def api_start_scan():
    """Start a new inspector scan (EXIF or integrity)."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON body"}), 400

    folder = data.get("folder", "").strip()
    mode = data.get("mode", "exif")

    if not folder or not os.path.isdir(folder):
        return jsonify({"error": f"Invalid folder: {folder}"}), 400
    if mode not in ("exif", "integrity"):
        return jsonify({"error": "mode must be 'exif' or 'integrity'"}), 400

    job_id = start_job(folder=folder, mode=mode)
    return jsonify({"job_id": job_id}), 202


@bp.route("/scan/<job_id>/status")
def api_scan_status(job_id: str):
    """Get status of an inspector job."""
    job = get_job(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    elapsed = 0.0
    if job.started_at:
        end = job.finished_at if job.finished_at else time.time()
        elapsed = end - job.started_at

    return jsonify({
        "id": job.id,
        "status": job.status,
        "mode": job.mode,
        "progress": job.progress,
        "message": job.message,
        "error": job.error,
        "total_files": job.total_files,
        "processed_files": job.processed_files,
        "elapsed_seconds": round(elapsed, 1),
    })


@bp.route("/scan/<job_id>/results")
def api_scan_results(job_id: str):
    """Get results of a completed inspector job."""
    job = get_job(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    if job.status not in ("done", "error"):
        return jsonify({"error": "Scan not finished yet"}), 409

    return jsonify({
        "mode": job.mode,
        "results": job.results,
        "total_files": job.total_files,
    })


# ── EXIF Edit ──────────────────────────────────────────────────────────────


@bp.route("/exif/edit", methods=["POST"])
def api_exif_edit():
    """Edit EXIF fields on a single file."""
    from morphic.inspector.exif import edit_exif

    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON body"}), 400

    file_path = data.get("file", "").strip()
    updates = data.get("updates", {})

    if not file_path or not os.path.isfile(file_path):
        return jsonify({"error": f"Invalid file: {file_path}"}), 400
    if not updates:
        return jsonify({"error": "No updates provided"}), 400

    try:
        edit_exif(file_path, updates)
        return jsonify({"status": "ok", "file": file_path})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── EXIF Strip ─────────────────────────────────────────────────────────────


@bp.route("/exif/strip", methods=["POST"])
def api_exif_strip():
    """Strip EXIF from one or more files."""
    from morphic.inspector.exif import strip_exif_batch

    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON body"}), 400

    files = data.get("files", [])
    if not files:
        return jsonify({"error": "No files specified"}), 400

    results = strip_exif_batch(files)
    success_count = sum(1 for r in results.values() if r.get("success"))
    return jsonify({
        "results": results,
        "total": len(files),
        "success_count": success_count,
    })

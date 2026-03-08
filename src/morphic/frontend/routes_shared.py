"""
Shared routes — index page, folder browsing, thumbnail & media serving.
"""

from __future__ import annotations

import mimetypes
import os
from pathlib import Path

from flask import (
    Blueprint,
    abort,
    current_app,
    jsonify,
    render_template,
    request,
    send_file,
)

from morphic.shared.constants import IMAGE_EXTENSIONS, VIDEO_EXTENSIONS
from morphic.shared.file_browser import open_native_folder_dialog
from morphic.shared.thumbnails import (
    generate_image_thumbnail,
    generate_video_thumbnail,
)
from morphic.shared.utils import normalise_ext

bp = Blueprint("shared", __name__)


# ── Page ────────────────────────────────────────────────────────────────────


@bp.route("/")
def index():
    """Serve the single-page application."""
    return render_template(
        "index.html",
        initial_folder=current_app.config.get("INITIAL_FOLDER", ""),
    )


# ── Directory browsing ─────────────────────────────────────────────────────


@bp.route("/api/browse")
def browse_directory():
    """List directories for the in-page folder browser."""
    path = request.args.get("path", str(Path.home()))
    try:
        path = os.path.expanduser(path)
        path = os.path.abspath(path)

        if not os.path.isdir(path):
            return jsonify({"error": "Not a directory"}), 400

        entries = []
        try:
            for entry in sorted(
                os.scandir(path), key=lambda e: e.name.lower(),
            ):
                if entry.name.startswith("."):
                    continue
                if entry.is_dir(follow_symlinks=False):
                    entries.append({
                        "name": entry.name,
                        "path": entry.path,
                        "type": "directory",
                    })
        except PermissionError:
            pass

        parent = os.path.dirname(path)
        return jsonify({
            "current": path,
            "parent": parent if parent != path else None,
            "entries": entries,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/browse/native", methods=["POST"])
def native_folder_dialog():
    """Open the OS-native folder picker dialog."""
    data = request.get_json(silent=True) or {}
    initial_dir = data.get("initial_dir", str(Path.home()))
    folder = open_native_folder_dialog(initial_dir)
    if folder:
        return jsonify({"folder": folder})
    return jsonify({
        "folder": None,
        "message": "Dialog cancelled or unavailable",
    }), 200


# ── Thumbnails & media ─────────────────────────────────────────────────────


@bp.route("/api/thumbnail")
def serve_thumbnail():
    """Generate and serve a thumbnail for a media file."""
    file_path = request.args.get("path", "")
    if not file_path or not os.path.isfile(file_path):
        abort(404)

    ext = normalise_ext(os.path.splitext(file_path)[1])

    try:
        if ext in IMAGE_EXTENSIONS:
            buf = generate_image_thumbnail(file_path)
            return send_file(buf, mimetype="image/jpeg")
        elif ext in VIDEO_EXTENSIONS:
            buf = generate_video_thumbnail(file_path)
            if buf:
                return send_file(buf, mimetype="image/jpeg")
            abort(404)
        else:
            abort(403)
    except Exception:
        abort(500)


@bp.route("/api/media")
def serve_media():
    """Serve a media file for full-size preview."""
    file_path = request.args.get("path", "")
    if not file_path or not os.path.isfile(file_path):
        abort(404)

    ext = normalise_ext(os.path.splitext(file_path)[1])
    allowed = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS
    if ext not in allowed:
        abort(403)

    mimetype = (
        mimetypes.guess_type(file_path)[0] or "application/octet-stream"
    )
    return send_file(file_path, mimetype=mimetype)

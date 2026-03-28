"""
Shared routes — index page, folder browsing, thumbnail & media serving.
"""

from __future__ import annotations

import importlib
import mimetypes
import os
import shutil
import subprocess
import sys
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
                os.scandir(path),
                key=lambda e: e.name.lower(),
            ):
                if entry.name.startswith("."):
                    continue
                if entry.is_dir(follow_symlinks=False):
                    entries.append(
                        {
                            "name": entry.name,
                            "path": entry.path,
                            "type": "directory",
                        }
                    )
        except PermissionError:
            pass

        parent = os.path.dirname(path)
        return jsonify(
            {
                "current": path,
                "parent": parent if parent != path else None,
                "entries": entries,
            }
        )
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
    return jsonify(
        {
            "folder": None,
            "message": "Dialog cancelled or unavailable",
        }
    ), 200


@bp.route("/api/system_info")
def api_system_info():
    """Return diagnostic info about GPU/cuda/ffmpeg availability."""
    info = {
        "python_version": sys.version,
        "torch": {
            "installed": False,
            "version": None,
            "cuda_available": False,
            "cuda_device_count": 0,
            "device_names": [],
        },
        "cupy": {
            "installed": False,
            "version": None,
            "device_count": 0,
        },
        "pyopencl": {
            "installed": False,
            "platforms": [],
        },
        "ffmpeg": {
            "installed": shutil.which("ffmpeg") is not None,
            "hwaccels": [],
            "encoders": [],
            "nvenc_available": False,
        },
        "duplicity_acceleration": {
            "backend": "unknown",
            "gpu_available": False,
        },
    }

    try:
        torch = importlib.import_module("torch")

        info["torch"].update(
            {
                "installed": True,
                "version": getattr(torch, "__version__", None),
                "cuda_available": bool(
                    getattr(
                        getattr(torch, "cuda", None),
                        "is_available",
                        lambda: False,
                    )()
                ),
                "cuda_device_count": torch.cuda.device_count()
                if getattr(
                    getattr(torch, "cuda", None), "is_available", lambda: False
                )()
                else 0,
                "device_names": [
                    torch.cuda.get_device_name(i)
                    for i in range(torch.cuda.device_count())
                ]
                if getattr(
                    getattr(torch, "cuda", None), "is_available", lambda: False
                )()
                else [],
            }
        )
    except Exception:
        pass

    try:
        cp = importlib.import_module("cupy")

        info["cupy"].update(
            {
                "installed": True,
                "version": getattr(cp, "__version__", None),
                "device_count": cp.cuda.runtime.getDeviceCount(),
            }
        )
    except Exception:
        pass

    try:
        cl = importlib.import_module("pyopencl")

        platforms = []
        for plat in cl.get_platforms():
            devices = [
                dev.name
                for dev in plat.get_devices(device_type=cl.device_type.GPU)
            ]
            platforms.append(
                {"name": plat.name, "vendor": plat.vendor, "devices": devices}
            )
        info["pyopencl"].update({"installed": True, "platforms": platforms})
    except Exception:
        pass

    if info["ffmpeg"]["installed"]:
        try:
            hw = subprocess.check_output(
                ["ffmpeg", "-hide_banner", "-hwaccels"],
                stderr=subprocess.STDOUT,
                text=True,
                timeout=10,
            )
            info["ffmpeg"]["hwaccels"] = [
                line.strip()
                for line in hw.splitlines()
                if line.strip() and line.strip().isdigit() is False
            ]
        except Exception:
            pass

        try:
            enc = subprocess.check_output(
                ["ffmpeg", "-hide_banner", "-encoders"],
                stderr=subprocess.STDOUT,
                text=True,
                timeout=15,
            )
            lines = [
                line.strip()
                for line in enc.splitlines()
                if line.strip() and line.strip()[0] in ("V", "A")
            ]
            info["ffmpeg"]["encoders"] = lines
            nvenc = [
                line
                for line in lines
                if "nvenc" in line
                or "h264_nvenc" in line
                or "hevc_nvenc" in line
            ]
            info["ffmpeg"]["nvenc_available"] = bool(nvenc)
        except Exception:
            pass

    try:
        from morphic.dupfinder.accelerator import get_accelerator

        acc = get_accelerator()
        info["duplicity_acceleration"]["backend"] = acc.get_backend_name()
        info["duplicity_acceleration"]["gpu_available"] = acc.is_gpu_available
    except Exception:
        pass

    return jsonify(info)


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

    mimetype = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
    return send_file(file_path, mimetype=mimetype)

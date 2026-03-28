"""Tests for morphic.frontend — app factory and routes."""

from __future__ import annotations

import importlib
import json
import os
import time

from PIL import Image

from morphic.frontend.app import create_app


# ── App factory ────────────────────────────────────────────────────────────


class TestCreateApp:
    def test_creates_flask_app(self) -> None:
        app = create_app()
        assert app is not None
        assert app.name == "morphic.frontend.app"

    def test_initial_folder_config(self) -> None:
        app = create_app(initial_folder="/test/path")
        assert app.config["INITIAL_FOLDER"] == "/test/path"

    def test_no_initial_folder(self) -> None:
        app = create_app()
        assert app.config["INITIAL_FOLDER"] == ""


# ── __main__.py ────────────────────────────────────────────────────────────


class TestMain:
    def test_main_module_exists(self) -> None:
        spec = importlib.util.find_spec("morphic.frontend.__main__")
        assert spec is not None


# ── Index ──────────────────────────────────────────────────────────────────


class TestIndexRoute:
    def test_returns_html(self, client) -> None:
        resp = client.get("/")
        assert resp.status_code == 200
        assert b"Morphic" in resp.data

    def test_has_tabs(self, client) -> None:
        resp = client.get("/")
        assert b"Converter" in resp.data
        assert b"Dupfinder" in resp.data
        assert b"Inspector" in resp.data
        assert b"Resizer" in resp.data
        assert b"Organizer" in resp.data

    def test_no_cache_headers(self, client) -> None:
        resp = client.get("/")
        assert "no-cache" in resp.headers.get("Cache-Control", "")


# ── Browse ─────────────────────────────────────────────────────────────────


class TestBrowseRoute:
    def test_browse_home(self, client) -> None:
        resp = client.get("/api/browse")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "current" in data
        assert "entries" in data

    def test_browse_specific_dir(self, client, tmp_path) -> None:
        sub = tmp_path / "testdir"
        sub.mkdir()
        resp = client.get(f"/api/browse?path={tmp_path}")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["current"] == str(tmp_path)
        names = [e["name"] for e in data["entries"]]
        assert "testdir" in names

    def test_browse_invalid_dir(self, client) -> None:
        resp = client.get("/api/browse?path=/nonexistent_xyz_path")
        assert resp.status_code == 400

    def test_browse_parent(self, client, tmp_path) -> None:
        resp = client.get(f"/api/browse?path={tmp_path}")
        data = resp.get_json()
        assert data["parent"] is not None or data["parent"] is None

    def test_native_browse_returns_json(self, client) -> None:
        resp = client.post(
            "/api/browse/native",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "folder" in data

    def test_system_info(self, client) -> None:
        resp = client.get("/api/system_info")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "ffmpeg" in data

    def test_browse_hidden_dirs_excluded(self, client, tmp_path) -> None:
        hidden = tmp_path / ".hidden"
        hidden.mkdir()
        visible = tmp_path / "visible"
        visible.mkdir()

        resp = client.get(f"/api/browse?path={tmp_path}")
        data = resp.get_json()
        names = [e["name"] for e in data["entries"]]
        assert "visible" in names
        assert ".hidden" not in names

    def test_browse_permission_error(self, client) -> None:
        resp = client.get("/api/browse?path=/root")
        assert resp.status_code in (200, 400, 500)

    def test_browse_tilde_expansion(self, client) -> None:
        resp = client.get("/api/browse?path=~")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "current" in data


# ── Thumbnail ──────────────────────────────────────────────────────────────


class TestThumbnailRoute:
    def test_nonexistent_file(self, client) -> None:
        resp = client.get("/api/thumbnail?path=/nonexistent/file.jpg")
        assert resp.status_code == 404

    def test_no_path_param(self, client) -> None:
        resp = client.get("/api/thumbnail")
        assert resp.status_code == 404

    def test_valid_image(self, client, test_image) -> None:
        resp = client.get(f"/api/thumbnail?path={test_image}")
        assert resp.status_code == 200
        assert resp.content_type == "image/jpeg"

    def test_forbidden_extension(self, client, tmp_path) -> None:
        txt = tmp_path / "test.txt"
        txt.write_text("hello")
        resp = client.get(f"/api/thumbnail?path={txt}")
        assert resp.status_code in (403, 500)

    def test_rgba_image_thumbnail(self, client, tmp_path) -> None:
        img_path = tmp_path / "rgba.png"
        Image.new("RGBA", (100, 100), (255, 0, 0, 128)).save(str(img_path))

        resp = client.get(f"/api/thumbnail?path={img_path}")
        assert resp.status_code == 200
        assert resp.content_type == "image/jpeg"

    def test_palette_image_thumbnail(self, client, tmp_path) -> None:
        img_path = tmp_path / "palette.gif"
        Image.new("P", (100, 100)).save(str(img_path))

        resp = client.get(f"/api/thumbnail?path={img_path}")
        assert resp.status_code == 200

    def test_thumbnail_video_file(self, client, tmp_path) -> None:
        vid = tmp_path / "test.mp4"
        vid.write_bytes(b"\x00" * 100)

        resp = client.get(f"/api/thumbnail?path={vid}")
        assert resp.status_code in (200, 404, 500)


# ── Media ──────────────────────────────────────────────────────────────────


class TestMediaRoute:
    def test_nonexistent_file(self, client) -> None:
        resp = client.get("/api/media?path=/nonexistent/file.jpg")
        assert resp.status_code == 404

    def test_valid_image(self, client, test_image) -> None:
        resp = client.get(f"/api/media?path={test_image}")
        assert resp.status_code == 200

    def test_forbidden_extension(self, client, tmp_path) -> None:
        txt = tmp_path / "test.txt"
        txt.write_text("hello")
        resp = client.get(f"/api/media?path={txt}")
        assert resp.status_code == 403

    def test_media_no_path(self, client) -> None:
        resp = client.get("/api/media")
        assert resp.status_code == 404

    def test_media_empty_path(self, client) -> None:
        resp = client.get("/api/media?path=")
        assert resp.status_code == 404

    def test_media_video_file(self, client, tmp_path) -> None:
        vid = tmp_path / "test.mp4"
        vid.write_bytes(b"\x00" * 100)

        resp = client.get(f"/api/media?path={vid}")
        assert resp.status_code == 200


class TestInspectorRoute:
    def test_inspector_scan(self, client, tmp_path) -> None:
        resp = client.post("/api/inspector/scan", json={})
        assert resp.status_code == 400

        resp = client.post(
            "/api/inspector/scan",
            json={"folder": str(tmp_path), "mode": "exif"},
        )
        assert resp.status_code == 202
        job_id = resp.get_json()["job_id"]

        status = client.get(f"/api/inspector/scan/{job_id}/status")
        assert status.status_code == 200

        results = client.get(f"/api/inspector/scan/{job_id}/results")
        assert results.status_code in (200, 409)

    def test_exif_edit_strip(self, client, tmp_path) -> None:
        resp = client.post("/api/inspector/exif/edit", json={})
        assert resp.status_code == 400

        resp = client.post("/api/inspector/exif/strip", json={})
        assert resp.status_code == 400


class TestOrganizerRoute:
    def test_organizer_plan_invalid(self, client, tmp_path) -> None:
        resp = client.post("/api/organizer/plan", json={})
        assert resp.status_code == 400

        resp = client.post(
            "/api/organizer/plan",
            json={
                "folder": str(tmp_path),
                "mode": "sort",
                "operation": "copy",
            },
        )
        assert resp.status_code == 202

    def test_organizer_status_not_found(self, client) -> None:
        resp = client.get("/api/organizer/status/notfound")
        assert resp.status_code == 404


class TestResizerRoute:
    def test_resizer_scan_invalid(self, client, tmp_path) -> None:
        resp = client.post("/api/resizer/scan", json={})
        assert resp.status_code == 400

        resp = client.post(
            "/api/resizer/scan",
            json={"folder": str(tmp_path), "width": 100, "height": 100},
        )
        assert resp.status_code == 202

    def test_resizer_status_results(self, client) -> None:
        resp = client.get("/api/resizer/scan/notfound/status")
        assert resp.status_code == 404

        resp = client.get("/api/resizer/scan/notfound/results")
        assert resp.status_code == 404


# ── Converter — scan ───────────────────────────────────────────────────────


class TestConverterScanRoute:
    def test_missing_folder(self, client) -> None:
        resp = client.post(
            "/api/converter/scan",
            data=json.dumps({"folder": ""}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_invalid_folder(self, client) -> None:
        resp = client.post(
            "/api/converter/scan",
            data=json.dumps({"folder": "/nonexistent_xyz"}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_valid_scan(self, client, tmp_media) -> None:
        resp = client.post(
            "/api/converter/scan",
            data=json.dumps({"folder": str(tmp_media)}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total"] > 0

    def test_no_body(self, client) -> None:
        resp = client.post("/api/converter/scan")
        assert resp.status_code in (400, 415)

    def test_scan_images_only(self, client, tmp_media) -> None:
        resp = client.post(
            "/api/converter/scan",
            data=json.dumps(
                {
                    "folder": str(tmp_media),
                    "filter_type": "images",
                }
            ),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        for f in data.get("files", []):
            ext = os.path.splitext(f["name"])[1].lower()
            assert ext not in {".mp4", ".mov", ".avi"}

    def test_scan_videos_only(self, client, tmp_media) -> None:
        resp = client.post(
            "/api/converter/scan",
            data=json.dumps(
                {
                    "folder": str(tmp_media),
                    "filter_type": "videos",
                }
            ),
            content_type="application/json",
        )
        assert resp.status_code == 200

    def test_scan_no_subfolders(self, client, tmp_media) -> None:
        resp = client.post(
            "/api/converter/scan",
            data=json.dumps(
                {
                    "folder": str(tmp_media),
                    "include_subfolders": False,
                }
            ),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        for f in data.get("files", []):
            assert "/sub/" not in f["path"]

    def test_scan_invalid_filter_type(self, client, tmp_media) -> None:
        resp = client.post(
            "/api/converter/scan",
            data=json.dumps(
                {
                    "folder": str(tmp_media),
                    "filter_type": "invalid",
                }
            ),
            content_type="application/json",
        )
        assert resp.status_code == 200


# ── Converter — formats ────────────────────────────────────────────────────


class TestConverterFormatsRoute:
    def test_returns_json(self, client) -> None:
        resp = client.get("/api/converter/formats")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "image" in data
        assert "video" in data

    def test_formats_structure(self, client) -> None:
        resp = client.get("/api/converter/formats")
        data = resp.get_json()
        assert isinstance(data["image"], dict)
        assert isinstance(data["video"], dict)
        for targets in data["image"].values():
            assert isinstance(targets, list)


# ── Converter — convert ────────────────────────────────────────────────────


class TestConverterConvertRoute:
    def test_no_files(self, client) -> None:
        resp = client.post(
            "/api/converter/convert",
            data=json.dumps({"files": [], "target_ext": ".png"}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_no_body(self, client) -> None:
        resp = client.post("/api/converter/convert")
        assert resp.status_code in (400, 415)

    def test_convert_single_file(self, client, test_image) -> None:
        resp = client.post(
            "/api/converter/convert",
            data=json.dumps(
                {
                    "files": [test_image],
                    "target_ext": ".png",
                }
            ),
            content_type="application/json",
        )
        assert resp.status_code == 202
        data = resp.get_json()
        assert "job_id" in data

    def test_convert_progress(self, client, test_image) -> None:
        resp = client.post(
            "/api/converter/convert",
            data=json.dumps(
                {
                    "files": [test_image],
                    "target_ext": ".png",
                }
            ),
            content_type="application/json",
        )
        job_id = resp.get_json()["job_id"]

        time.sleep(0.5)
        resp = client.get(f"/api/converter/progress/{job_id}")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "status" in data
        assert "completed" in data

    def test_missing_target_ext(self, client, test_image) -> None:
        resp = client.post(
            "/api/converter/convert",
            data=json.dumps(
                {
                    "files": [test_image],
                    "target_ext": "",
                }
            ),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_convert_with_delete(self, client, tmp_path) -> None:
        src = tmp_path / "test.jpg"
        Image.new("RGB", (50, 50), "red").save(str(src))

        resp = client.post(
            "/api/converter/convert",
            data=json.dumps(
                {
                    "files": [str(src)],
                    "target_ext": ".png",
                    "delete_original": True,
                }
            ),
            content_type="application/json",
        )
        assert resp.status_code == 202

        job_id = resp.get_json()["job_id"]
        time.sleep(1)

        resp = client.get(f"/api/converter/progress/{job_id}")
        data = resp.get_json()
        assert data["status"] == "done"

    def test_progress_poll(self, client, test_image) -> None:
        resp = client.post(
            "/api/converter/convert",
            data=json.dumps(
                {
                    "files": [test_image],
                    "target_ext": ".png",
                }
            ),
            content_type="application/json",
        )
        job_id = resp.get_json()["job_id"]
        time.sleep(0.5)

        resp = client.get(
            f"/api/converter/progress/{job_id}/poll?last=0",
        )
        assert resp.status_code == 200

    def test_progress_poll_nonexistent(self, client) -> None:
        resp = client.get("/api/converter/progress/nonexistent/poll")
        assert resp.status_code == 404

    def test_convert_nonexistent_source(self, client) -> None:
        resp = client.post(
            "/api/converter/convert",
            data=json.dumps(
                {
                    "files": ["/nonexistent/file.jpg"],
                    "target_ext": ".png",
                }
            ),
            content_type="application/json",
        )
        assert resp.status_code == 202
        job_id = resp.get_json()["job_id"]

        time.sleep(1)
        resp = client.get(f"/api/converter/progress/{job_id}")
        data = resp.get_json()
        assert data["status"] == "done"
        assert data["results"][0]["status"] == "error"

    def test_convert_multiple_files(self, client, tmp_path) -> None:
        files = []
        for i in range(3):
            src = tmp_path / f"img{i}.jpg"
            Image.new("RGB", (50, 50), "red").save(str(src))
            files.append(str(src))

        resp = client.post(
            "/api/converter/convert",
            data=json.dumps(
                {
                    "files": files,
                    "target_ext": ".png",
                }
            ),
            content_type="application/json",
        )
        assert resp.status_code == 202
        job_id = resp.get_json()["job_id"]

        for _ in range(20):
            time.sleep(0.3)
            resp = client.get(f"/api/converter/progress/{job_id}")
            data = resp.get_json()
            if data["status"] == "done":
                break

        assert data["completed"] == 3
        assert all(r["status"] == "ok" for r in data["results"])

    def test_convert_with_size_info(self, client, tmp_path) -> None:
        src = tmp_path / "test.jpg"
        Image.new("RGB", (100, 100), "blue").save(str(src))

        resp = client.post(
            "/api/converter/convert",
            data=json.dumps(
                {
                    "files": [str(src)],
                    "target_ext": ".png",
                }
            ),
            content_type="application/json",
        )
        job_id = resp.get_json()["job_id"]

        time.sleep(1)
        resp = client.get(f"/api/converter/progress/{job_id}")
        data = resp.get_json()
        result = data["results"][0]
        assert "original_size" in result
        assert "new_size" in result
        assert "original_size_fmt" in result
        assert "new_size_fmt" in result


# ── Converter — delete ─────────────────────────────────────────────────────


class TestConverterDeleteRoute:
    def test_no_files(self, client) -> None:
        resp = client.post(
            "/api/converter/delete",
            data=json.dumps({"files": []}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_delete_nonexistent(self, client) -> None:
        resp = client.post(
            "/api/converter/delete",
            data=json.dumps({"files": ["/nonexistent/file.jpg"]}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["results"][0]["status"] == "not_found"

    def test_delete_real_file(self, client, tmp_path) -> None:
        f = tmp_path / "deleteme.jpg"
        Image.new("RGB", (10, 10), "red").save(str(f))
        assert f.exists()

        resp = client.post(
            "/api/converter/delete",
            data=json.dumps({"files": [str(f)]}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["results"][0]["status"] == "deleted"
        assert not f.exists()

    def test_delete_no_body(self, client) -> None:
        resp = client.post("/api/converter/delete")
        assert resp.status_code in (400, 415)

    def test_delete_without_files_key(self, client) -> None:
        resp = client.post(
            "/api/converter/delete",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_delete_mixed_results(self, client, tmp_path) -> None:
        real = tmp_path / "real.jpg"
        Image.new("RGB", (10, 10), "red").save(str(real))

        resp = client.post(
            "/api/converter/delete",
            data=json.dumps(
                {
                    "files": [str(real), "/nonexistent/file.jpg"],
                }
            ),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["results"][0]["status"] == "deleted"
        assert data["results"][1]["status"] == "not_found"
        assert data["total_freed"] > 0


# ── Converter — progress ───────────────────────────────────────────────────


class TestConverterProgressRoute:
    def test_nonexistent_job(self, client) -> None:
        resp = client.get("/api/converter/progress/nonexistent")
        assert resp.status_code == 404


# ── Dupfinder — scan ───────────────────────────────────────────────────────


class TestDupfinderScanRoute:
    def test_missing_folder(self, client) -> None:
        resp = client.post(
            "/api/dupfinder/scan",
            data=json.dumps({"folder": ""}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_invalid_scan_type(self, client, tmp_path) -> None:
        resp = client.post(
            "/api/dupfinder/scan",
            data=json.dumps(
                {
                    "folder": str(tmp_path),
                    "type": "invalid",
                }
            ),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_no_body(self, client) -> None:
        resp = client.post("/api/dupfinder/scan")
        assert resp.status_code in (400, 415)

    def test_valid_scan_start(self, client, tmp_path) -> None:
        resp = client.post(
            "/api/dupfinder/scan",
            data=json.dumps(
                {
                    "folder": str(tmp_path),
                    "type": "images",
                }
            ),
            content_type="application/json",
        )
        assert resp.status_code == 202
        data = resp.get_json()
        assert "job_id" in data

    def test_scan_with_thresholds(self, client, tmp_path) -> None:
        resp = client.post(
            "/api/dupfinder/scan",
            data=json.dumps(
                {
                    "folder": str(tmp_path),
                    "type": "both",
                    "image_threshold": 0.95,
                    "video_threshold": 0.80,
                }
            ),
            content_type="application/json",
        )
        assert resp.status_code == 202

    def test_scan_status_after_start(self, client, tmp_path) -> None:
        resp = client.post(
            "/api/dupfinder/scan",
            data=json.dumps(
                {
                    "folder": str(tmp_path),
                    "type": "images",
                }
            ),
            content_type="application/json",
        )
        job_id = resp.get_json()["job_id"]

        resp = client.get(f"/api/dupfinder/scan/{job_id}/status")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "status" in data
        assert "progress" in data

    def test_scan_results_not_done(self, client, tmp_path) -> None:
        resp = client.post(
            "/api/dupfinder/scan",
            data=json.dumps(
                {
                    "folder": str(tmp_path),
                    "type": "images",
                }
            ),
            content_type="application/json",
        )
        job_id = resp.get_json()["job_id"]

        resp = client.get(f"/api/dupfinder/scan/{job_id}/results")
        assert resp.status_code in (200, 409)

    def test_scan_results_after_completion(self, client, tmp_path) -> None:
        resp = client.post(
            "/api/dupfinder/scan",
            data=json.dumps(
                {
                    "folder": str(tmp_path),
                    "type": "images",
                }
            ),
            content_type="application/json",
        )
        job_id = resp.get_json()["job_id"]

        for _ in range(20):
            time.sleep(0.5)
            resp = client.get(f"/api/dupfinder/scan/{job_id}/status")
            data = resp.get_json()
            if data["status"] in ("done", "error"):
                break

        resp = client.get(f"/api/dupfinder/scan/{job_id}/results")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "image_groups" in data
        assert "space_savings" in data

    def test_scan_videos_only(self, client, tmp_path) -> None:
        resp = client.post(
            "/api/dupfinder/scan",
            data=json.dumps(
                {
                    "folder": str(tmp_path),
                    "type": "videos",
                }
            ),
            content_type="application/json",
        )
        assert resp.status_code == 202

    def test_scan_both_types(self, client, tmp_path) -> None:
        resp = client.post(
            "/api/dupfinder/scan",
            data=json.dumps(
                {
                    "folder": str(tmp_path),
                    "type": "both",
                }
            ),
            content_type="application/json",
        )
        assert resp.status_code == 202


# ── Dupfinder — status / results ───────────────────────────────────────────


class TestDupfinderStatusRoute:
    def test_nonexistent_job(self, client) -> None:
        resp = client.get("/api/dupfinder/scan/nonexistent/status")
        assert resp.status_code == 404


class TestDupfinderResultsRoute:
    def test_nonexistent_job(self, client) -> None:
        resp = client.get("/api/dupfinder/scan/nonexistent/results")
        assert resp.status_code == 404


# ── Dupfinder — delete ─────────────────────────────────────────────────────


class TestDupfinderDeleteRoute:
    def test_no_files(self, client) -> None:
        resp = client.post(
            "/api/dupfinder/delete",
            data=json.dumps({"files": []}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_delete_nonexistent(self, client) -> None:
        resp = client.post(
            "/api/dupfinder/delete",
            data=json.dumps({"files": ["/nonexistent/file.jpg"]}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["results"][0]["status"] == "not_found"

    def test_no_body(self, client) -> None:
        resp = client.post("/api/dupfinder/delete")
        assert resp.status_code in (400, 415)

    def test_delete_without_files_key(self, client) -> None:
        resp = client.post(
            "/api/dupfinder/delete",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_delete_real_file(self, client, tmp_path) -> None:
        f = tmp_path / "dup.jpg"
        Image.new("RGB", (10, 10), "red").save(str(f))

        resp = client.post(
            "/api/dupfinder/delete",
            data=json.dumps({"files": [str(f)]}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["results"][0]["status"] == "deleted"
        assert not f.exists()

    def test_delete_mixed(self, client, tmp_path) -> None:
        f = tmp_path / "real.jpg"
        Image.new("RGB", (10, 10), "red").save(str(f))

        resp = client.post(
            "/api/dupfinder/delete",
            data=json.dumps(
                {
                    "files": [str(f), "/nonexistent.jpg"],
                }
            ),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["results"]) == 2


# ── Inspector Routes ──────────────────────────────────────────────────────


class TestInspectorRoutes:
    def test_scan_requires_folder(self, client) -> None:
        resp = client.post(
            "/api/inspector/scan",
            data=json.dumps({"mode": "exif"}),
            content_type="application/json",
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data

    def test_scan_exif(self, client, tmp_path) -> None:
        Image.new("RGB", (10, 10)).save(str(tmp_path / "a.jpg"), "JPEG")
        resp = client.post(
            "/api/inspector/scan",
            data=json.dumps({"folder": str(tmp_path), "mode": "exif"}),
            content_type="application/json",
        )
        assert resp.status_code == 202
        data = resp.get_json()
        assert "job_id" in data

    def test_scan_integrity(self, client, tmp_path) -> None:
        Image.new("RGB", (10, 10)).save(str(tmp_path / "a.jpg"), "JPEG")
        resp = client.post(
            "/api/inspector/scan",
            data=json.dumps({"folder": str(tmp_path), "mode": "integrity"}),
            content_type="application/json",
        )
        assert resp.status_code == 202
        data = resp.get_json()
        assert "job_id" in data

    def test_status_unknown_job(self, client) -> None:
        resp = client.get("/api/inspector/scan/fakeid/status")
        assert resp.status_code == 404
        data = resp.get_json()
        assert "error" in data

    def test_strip_requires_files(self, client) -> None:
        resp = client.post(
            "/api/inspector/exif/strip",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data


# ── Resizer Routes ────────────────────────────────────────────────────────


class TestResizerRoutes:
    def test_scan_requires_folder(self, client) -> None:
        resp = client.post(
            "/api/resizer/scan",
            data=json.dumps({"width": 100, "height": 100}),
            content_type="application/json",
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data

    def test_scan_starts_job(self, client, tmp_path) -> None:
        Image.new("RGB", (100, 100)).save(str(tmp_path / "img.png"))
        resp = client.post(
            "/api/resizer/scan",
            data=json.dumps(
                {
                    "folder": str(tmp_path),
                    "width": 50,
                    "height": 50,
                    "mode": "fit",
                }
            ),
            content_type="application/json",
        )
        assert resp.status_code == 202
        data = resp.get_json()
        assert "job_id" in data

    def test_status_unknown_job(self, client) -> None:
        resp = client.get("/api/resizer/scan/fakeid/status")
        assert resp.status_code == 404
        data = resp.get_json()
        assert "error" in data


# ── Organizer Routes ──────────────────────────────────────────────────────


class TestOrganizerRoutes:
    def test_plan_requires_folder(self, client) -> None:
        resp = client.post(
            "/api/organizer/plan",
            data=json.dumps({"mode": "sort"}),
            content_type="application/json",
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data

    def test_plan_sort(self, client, tmp_path) -> None:
        Image.new("RGB", (10, 10)).save(str(tmp_path / "photo.jpg"), "JPEG")
        resp = client.post(
            "/api/organizer/plan",
            data=json.dumps(
                {
                    "folder": str(tmp_path),
                    "mode": "sort",
                    "operation": "copy",
                    "template": "{year}/{month}",
                }
            ),
            content_type="application/json",
        )
        assert resp.status_code == 202
        data = resp.get_json()
        assert "job_id" in data

    def test_execute_requires_job_id(self, client) -> None:
        resp = client.post(
            "/api/organizer/execute",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data

    def test_status_unknown_job(self, client) -> None:
        resp = client.get("/api/organizer/status/fakeid")
        assert resp.status_code == 404
        data = resp.get_json()
        assert "error" in data

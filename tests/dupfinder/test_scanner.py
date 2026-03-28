"""Tests for morphic.dupfinder.scanner."""

from __future__ import annotations

import time

from PIL import Image

from morphic.dupfinder.images import ImageInfo
from morphic.dupfinder.scanner import (
    ScanJob,
    _calculate_space_savings,
    _format_image_groups,
    _format_video_groups,
    _run_scan,
    get_job,
    start_job,
)
from morphic.dupfinder.videos import VideoInfo


# ── ScanJob ────────────────────────────────────────────────────────────────


class TestScanJob:
    def test_defaults(self) -> None:
        job = ScanJob(id="test", folder="/tmp", scan_type="both")
        assert job.status == "pending"
        assert job.progress == 0.0
        assert job.image_groups == []
        assert job.video_groups == []

    def test_custom_thresholds(self) -> None:
        job = ScanJob(
            id="test",
            folder="/tmp",
            scan_type="images",
            image_threshold=0.95,
            video_threshold=0.80,
        )
        assert job.image_threshold == 0.95
        assert job.video_threshold == 0.80


# ── get_job / start_job ────────────────────────────────────────────────────


class TestGetJob:
    def test_nonexistent_job(self) -> None:
        result = get_job("nonexistent-id-xyz")
        assert result is None


class TestStartJob:
    def test_returns_job_id(self, tmp_path) -> None:
        job_id = start_job(
            folder=str(tmp_path),
            scan_type="images",
        )
        assert isinstance(job_id, str)
        assert len(job_id) == 8

    def test_job_is_retrievable(self, tmp_path) -> None:
        job_id = start_job(
            folder=str(tmp_path),
            scan_type="images",
        )
        time.sleep(0.2)
        job = get_job(job_id)
        assert job is not None
        assert job.folder == str(tmp_path)
        assert job.scan_type == "images"

    def test_custom_thresholds(self, tmp_path) -> None:
        job_id = start_job(
            folder=str(tmp_path),
            scan_type="both",
            image_threshold=0.95,
            video_threshold=0.80,
        )
        job = get_job(job_id)
        assert job is not None
        assert job.image_threshold == 0.95
        assert job.video_threshold == 0.80


# ── _run_scan ──────────────────────────────────────────────────────────────


class TestRunScan:
    def test_scan_empty_folder(self, tmp_path) -> None:
        job = ScanJob(
            id="test-empty",
            folder=str(tmp_path),
            scan_type="images",
        )
        _run_scan(job)
        assert job.status == "done"
        assert job.progress == 1.0
        assert len(job.image_groups) == 0
        assert job.finished_at > 0

    def test_scan_videos_type(self, tmp_path) -> None:
        job = ScanJob(
            id="test-vid",
            folder=str(tmp_path),
            scan_type="videos",
        )
        _run_scan(job)
        assert job.status == "done"

    def test_scan_both_type(self, tmp_path) -> None:
        job = ScanJob(
            id="test-both",
            folder=str(tmp_path),
            scan_type="both",
        )
        _run_scan(job)
        assert job.status == "done"
        assert "Done!" in job.message

    def test_scan_nonexistent_folder(self) -> None:
        job = ScanJob(
            id="test-bad",
            folder="/nonexistent_folder_xyz",
            scan_type="images",
        )
        _run_scan(job)
        assert job.status in ("done", "error")

    def test_scan_folder_with_images(self, tmp_path) -> None:
        for name in ["a.jpg", "b.jpg", "c.jpg"]:
            Image.new("RGB", (50, 50), "red").save(str(tmp_path / name))

        job = ScanJob(
            id="test-imgs",
            folder=str(tmp_path),
            scan_type="images",
        )
        _run_scan(job)

        assert job.status == "done"
        assert job.total_files_found >= 3
        assert job.total_files_processed >= 3
        assert job.finished_at > job.started_at
        assert "Done!" in job.message

    def test_scan_folder_with_duplicates(self, tmp_path) -> None:
        for name in ["a.jpg", "b.jpg"]:
            Image.new("RGB", (50, 50), "red").save(str(tmp_path / name))

        job = ScanJob(
            id="test-dups",
            folder=str(tmp_path),
            scan_type="images",
            image_threshold=0.9,
        )
        _run_scan(job)

        assert job.status == "done"
        assert len(job.image_groups) >= 1

    def test_scan_both_image_and_video(self, tmp_path) -> None:
        Image.new("RGB", (50, 50), "red").save(str(tmp_path / "img.jpg"))
        (tmp_path / "vid.mp4").write_bytes(b"\x00" * 100)

        job = ScanJob(
            id="test-both",
            folder=str(tmp_path),
            scan_type="both",
        )
        _run_scan(job)

        assert job.status == "done"
        assert job.progress == 1.0

    def test_scan_progress_tracking(self, tmp_path) -> None:
        Image.new("RGB", (10, 10), "red").save(str(tmp_path / "a.jpg"))

        job = ScanJob(
            id="test-prog",
            folder=str(tmp_path),
            scan_type="images",
        )
        _run_scan(job)

        assert job.progress == 1.0
        assert job.total_files_found >= 1
        assert job.space_savings >= 0

    def test_scan_message_updates(self, tmp_path) -> None:
        for i in range(3):
            Image.new("RGB", (50, 50), "blue").save(
                str(tmp_path / f"img{i}.jpg"),
            )

        job = ScanJob(
            id="test-msg",
            folder=str(tmp_path),
            scan_type="images",
        )
        _run_scan(job)

        assert "Done!" in job.message or "Error" in job.message


# ── _format_image_groups ───────────────────────────────────────────────────


class TestFormatImageGroups:
    def test_empty_groups(self) -> None:
        result = _format_image_groups([], {})
        assert result == []

    def test_formats_group(self) -> None:
        infos = {
            "/a.jpg": ImageInfo(
                path="/a.jpg",
                width=1920,
                height=1080,
                format="JPEG",
                file_size=100000,
            ),
            "/b.jpg": ImageInfo(
                path="/b.jpg",
                width=1920,
                height=1080,
                format="JPEG",
                file_size=50000,
            ),
        }
        groups = [[("/a.jpg", 1.0), ("/b.jpg", 0.95)]]
        result = _format_image_groups(groups, infos)
        assert len(result) == 1
        assert len(result[0]) == 2
        assert result[0][0]["path"] == "/a.jpg"
        assert result[0][0]["type"] == "image"
        assert result[0][1]["similarity"] == 95.0

    def test_single_item_group_filtered(self) -> None:
        infos = {
            "/a.jpg": ImageInfo(
                path="/a.jpg",
                width=100,
                height=100,
                format="JPEG",
                file_size=1000,
            ),
        }
        groups = [[("/a.jpg", 1.0)]]
        result = _format_image_groups(groups, infos)
        assert result == []

    def test_missing_info_skipped(self) -> None:
        infos = {
            "/a.jpg": ImageInfo(
                path="/a.jpg",
                width=100,
                height=100,
                format="JPEG",
                file_size=1000,
            ),
        }
        groups = [[("/a.jpg", 1.0), ("/b.jpg", 0.95)]]
        result = _format_image_groups(groups, infos)
        assert result == []

    def test_three_items(self) -> None:
        infos = {
            f"/{n}.jpg": ImageInfo(
                path=f"/{n}.jpg",
                width=100,
                height=100,
                format="JPEG",
                file_size=i * 1000,
            )
            for i, n in enumerate(["a", "b", "c"], 1)
        }
        groups = [[("/a.jpg", 1.0), ("/b.jpg", 0.95), ("/c.jpg", 0.92)]]
        result = _format_image_groups(groups, infos)
        assert len(result) == 1
        assert len(result[0]) == 3


# ── _format_video_groups ───────────────────────────────────────────────────


class TestFormatVideoGroups:
    def test_empty_groups(self) -> None:
        result = _format_video_groups([], {})
        assert result == []

    def test_formats_group(self) -> None:
        infos = {
            "/a.mp4": VideoInfo(
                path="/a.mp4",
                width=1920,
                height=1080,
                duration=120.0,
                fps=30.0,
                file_size=5000000,
            ),
            "/b.mp4": VideoInfo(
                path="/b.mp4",
                width=1920,
                height=1080,
                duration=120.0,
                fps=30.0,
                file_size=3000000,
            ),
        }
        groups = [[("/a.mp4", 1.0), ("/b.mp4", 0.88)]]
        result = _format_video_groups(groups, infos)
        assert len(result) == 1
        assert len(result[0]) == 2
        assert result[0][0]["path"] == "/a.mp4"
        assert result[0][0]["type"] == "video"
        assert "duration_formatted" in result[0][0]

    def test_missing_info_skipped(self) -> None:
        infos = {
            "/a.mp4": VideoInfo(
                path="/a.mp4",
                width=1920,
                height=1080,
                duration=60.0,
                fps=30.0,
                file_size=5000000,
            ),
        }
        groups = [[("/a.mp4", 1.0), ("/b.mp4", 0.88)]]
        result = _format_video_groups(groups, infos)
        assert result == []


# ── _calculate_space_savings ───────────────────────────────────────────────


class TestCalculateSpaceSavings:
    def test_no_groups(self) -> None:
        job = ScanJob(id="x", folder="/tmp", scan_type="both")
        assert _calculate_space_savings(job) == 0

    def test_with_groups(self) -> None:
        job = ScanJob(id="x", folder="/tmp", scan_type="both")
        job.image_groups = [
            [
                {"file_size": 100000, "path": "/a.jpg"},
                {"file_size": 50000, "path": "/b.jpg"},
            ]
        ]
        savings = _calculate_space_savings(job)
        assert savings == 50000

    def test_multiple_groups(self) -> None:
        job = ScanJob(id="x", folder="/tmp", scan_type="both")
        job.image_groups = [
            [
                {"file_size": 10000, "path": "/a.jpg"},
                {"file_size": 5000, "path": "/b.jpg"},
            ],
        ]
        job.video_groups = [
            [
                {"file_size": 20000, "path": "/a.mp4"},
                {"file_size": 15000, "path": "/b.mp4"},
            ],
        ]
        savings = _calculate_space_savings(job)
        assert savings == 5000 + 15000

    def test_three_files_in_group(self) -> None:
        job = ScanJob(id="x", folder="/tmp", scan_type="both")
        job.image_groups = [
            [
                {"file_size": 10000, "path": "/a.jpg"},
                {"file_size": 8000, "path": "/b.jpg"},
                {"file_size": 5000, "path": "/c.jpg"},
            ],
        ]
        savings = _calculate_space_savings(job)
        assert savings == 13000

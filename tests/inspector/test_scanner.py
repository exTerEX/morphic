"""Tests for morphic.inspector.scanner."""

from __future__ import annotations

from PIL import Image

from morphic.inspector.scanner import get_job, start_job


def _make_jpeg(path, size=(20, 20)):
    Image.new("RGB", size, "red").save(str(path), "JPEG")


class TestInspectorScanner:
    def test_start_exif_scan(self, tmp_path) -> None:
        _make_jpeg(tmp_path / "a.jpg")
        _make_jpeg(tmp_path / "b.jpg")

        job_id = start_job(str(tmp_path), mode="exif")
        assert isinstance(job_id, str)

        # Poll until done
        import time
        for _ in range(50):
            job = get_job(job_id)
            if job and job.status in ("done", "error"):
                break
            time.sleep(0.1)

        job = get_job(job_id)
        assert job is not None
        assert job.status == "done"
        assert len(job.results) == 2

    def test_start_integrity_scan(self, tmp_path) -> None:
        _make_jpeg(tmp_path / "ok.jpg")
        # Truncated file
        bad = tmp_path / "bad.jpg"
        bad.write_bytes(b"\xff\xd8" + b"\x00" * 5)

        job_id = start_job(str(tmp_path), mode="integrity")

        import time
        for _ in range(50):
            job = get_job(job_id)
            if job and job.status in ("done", "error"):
                break
            time.sleep(0.1)

        job = get_job(job_id)
        assert job is not None
        assert job.status == "done"
        assert len(job.results) >= 2

    def test_get_nonexistent_job(self) -> None:
        assert get_job("nonexistent-id") is None

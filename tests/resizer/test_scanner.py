"""Tests for morphic.resizer.scanner."""

from __future__ import annotations

import time

from PIL import Image

from morphic.resizer.scanner import get_job, start_job


def _make_images(tmp_path, count=3):
    for i in range(count):
        Image.new("RGB", (200, 100), "green").save(
            str(tmp_path / f"img{i}.png")
        )


class TestResizerScanner:
    def test_start_job(self, tmp_path) -> None:
        _make_images(tmp_path)
        out = tmp_path / "output"

        job_id = start_job(
            folder=str(tmp_path),
            width=50,
            height=50,
            mode="fit",
            output_folder=str(out),
        )
        assert isinstance(job_id, str)

        for _ in range(50):
            job = get_job(job_id)
            if job and job.status in ("done", "error"):
                break
            time.sleep(0.1)

        job = get_job(job_id)
        assert job is not None
        assert job.status == "done"
        assert len(job.results) == 3

    def test_nonexistent_job(self) -> None:
        assert get_job("fake-id") is None

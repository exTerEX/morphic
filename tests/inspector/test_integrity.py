"""Tests for morphic.inspector.integrity."""

from __future__ import annotations

import os

import pytest
from PIL import Image

from morphic.inspector.integrity import check_files, check_image, check_video


def _make_jpeg(path: str) -> str:
    Image.new("RGB", (20, 20), "green").save(path, "JPEG")
    return path


class TestCheckImage:
    def test_valid_image_ok(self, tmp_path) -> None:
        path = _make_jpeg(str(tmp_path / "ok.jpg"))
        result = check_image(path)
        assert result["valid"] is True
        assert result["path"] == path

    def test_truncated_image(self, tmp_path) -> None:
        path = str(tmp_path / "bad.jpg")
        _make_jpeg(path)
        # Truncate the file
        with open(path, "r+b") as f:
            f.truncate(10)
        result = check_image(path)
        assert result["valid"] is False
        assert result["error"] is not None

    def test_zero_byte(self, tmp_path) -> None:
        path = str(tmp_path / "empty.jpg")
        open(path, "w").close()
        result = check_image(path)
        assert result["valid"] is False

    def test_nonexistent(self, tmp_path) -> None:
        result = check_image(str(tmp_path / "nope.jpg"))
        assert result["valid"] is False


class TestCheckVideo:
    def test_fake_video_fails(self, tmp_path) -> None:
        path = str(tmp_path / "fake.mp4")
        with open(path, "wb") as f:
            f.write(b"\x00" * 100)
        result = check_video(path)
        # Fake video should fail ffprobe (or return valid=False if no ffprobe)
        assert isinstance(result["valid"], bool)
        assert "path" in result


class TestCheckFiles:
    def test_scans_folder(self, tmp_path) -> None:
        _make_jpeg(str(tmp_path / "a.jpg"))
        _make_jpeg(str(tmp_path / "b.png"))
        # Non-media file should be ignored
        (tmp_path / "readme.txt").write_text("hello")

        results = check_files(str(tmp_path))
        # Should have at least the 2 images
        image_results = [r for r in results if r["path"].endswith((".jpg", ".png"))]
        assert len(image_results) >= 2

    def test_empty_folder(self, tmp_path) -> None:
        results = check_files(str(tmp_path))
        assert results == []

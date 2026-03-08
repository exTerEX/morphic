"""Tests for morphic.shared.thumbnails."""

from __future__ import annotations

import io
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from morphic.shared.thumbnails import (
    generate_image_thumbnail,
    generate_video_thumbnail,
)


class TestGenerateImageThumbnail:
    def test_basic(self, tmp_path) -> None:
        img_path = tmp_path / "test.jpg"
        Image.new("RGB", (500, 500), "red").save(str(img_path))

        buf = generate_image_thumbnail(str(img_path), size=100)
        assert isinstance(buf, io.BytesIO)

        result = Image.open(buf)
        assert result.format == "JPEG"
        assert max(result.size) <= 100

    def test_large_image(self, tmp_path) -> None:
        img_path = tmp_path / "large.png"
        Image.new("RGB", (3000, 2000), "blue").save(str(img_path))

        buf = generate_image_thumbnail(str(img_path), size=300)
        result = Image.open(buf)
        assert max(result.size) <= 300

    def test_rgba_converts_to_rgb(self, tmp_path) -> None:
        img_path = tmp_path / "rgba.png"
        Image.new("RGBA", (100, 100), (255, 0, 0, 128)).save(str(img_path))

        buf = generate_image_thumbnail(str(img_path))
        result = Image.open(buf)
        assert result.mode == "RGB"

    def test_palette_converts(self, tmp_path) -> None:
        img_path = tmp_path / "palette.gif"
        Image.new("P", (100, 100)).save(str(img_path))

        buf = generate_image_thumbnail(str(img_path))
        result = Image.open(buf)
        assert result.mode == "RGB"

    def test_la_mode_converts(self, tmp_path) -> None:
        img_path = tmp_path / "la.png"
        Image.new("LA", (100, 100)).save(str(img_path))

        buf = generate_image_thumbnail(str(img_path))
        result = Image.open(buf)
        assert result.mode == "RGB"

    def test_custom_size(self, tmp_path) -> None:
        img_path = tmp_path / "test.jpg"
        Image.new("RGB", (1000, 1000), "green").save(str(img_path))

        buf = generate_image_thumbnail(str(img_path), size=150)
        result = Image.open(buf)
        assert max(result.size) <= 150

    def test_nonexistent_file(self) -> None:
        with pytest.raises(Exception):
            generate_image_thumbnail("/nonexistent/file.jpg")


class TestGenerateVideoThumbnail:
    @patch("morphic.shared.thumbnails.subprocess.run")
    def test_success(self, mock_run) -> None:
        img = Image.new("RGB", (100, 100), "red")
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        jpeg_bytes = buf.getvalue()

        mock_run.return_value = MagicMock(
            returncode=0, stdout=jpeg_bytes,
        )
        result = generate_video_thumbnail("/test/video.mp4")
        assert result is not None
        assert isinstance(result, io.BytesIO)

    @patch("morphic.shared.thumbnails.subprocess.run")
    def test_failure(self, mock_run) -> None:
        mock_run.return_value = MagicMock(returncode=1, stdout=b"")
        result = generate_video_thumbnail("/test/video.mp4")
        assert result is None

    @patch("morphic.shared.thumbnails.subprocess.run")
    def test_retry_at_0s(self, mock_run) -> None:
        img = Image.new("RGB", (100, 100), "blue")
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        jpeg_bytes = buf.getvalue()

        mock_run.side_effect = [
            MagicMock(returncode=1, stdout=b""),
            MagicMock(returncode=0, stdout=jpeg_bytes),
        ]
        result = generate_video_thumbnail("/test/short.mp4")
        assert result is not None
        assert mock_run.call_count == 2

    @patch("morphic.shared.thumbnails.subprocess.run")
    def test_custom_size(self, mock_run) -> None:
        img = Image.new("RGB", (50, 50), "green")
        buf = io.BytesIO()
        img.save(buf, format="JPEG")

        mock_run.return_value = MagicMock(
            returncode=0, stdout=buf.getvalue(),
        )
        result = generate_video_thumbnail("/test/video.mp4", size=150)
        assert result is not None

    def test_nonexistent_file(self) -> None:
        result = generate_video_thumbnail("/nonexistent/file.mp4")
        assert result is None

    def test_invalid_video(self, tmp_path) -> None:
        fake = tmp_path / "fake.mp4"
        fake.write_bytes(b"\x00" * 10)
        result = generate_video_thumbnail(str(fake))
        assert result is None

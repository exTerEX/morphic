"""Tests for morphic.converter.converter."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from morphic.converter import converter
from morphic.converter.converter import (
    _ffmpeg_available,
    convert_file,
    convert_image,
    convert_video,
)


class TestFfmpegAvailable:
    def test_returns_bool(self) -> None:
        result = _ffmpeg_available()
        assert isinstance(result, bool)


class TestConvertImage:
    def test_jpg_to_png(self, tmp_path) -> None:
        src = tmp_path / "test.jpg"
        Image.new("RGB", (50, 50), "red").save(str(src))

        dest = convert_image(str(src), ".png")
        assert os.path.isfile(dest)
        assert dest.endswith(".png")

    def test_png_to_jpg(self, tmp_path) -> None:
        src = tmp_path / "test.png"
        Image.new("RGB", (50, 50), "blue").save(str(src))

        dest = convert_image(str(src), ".jpg")
        assert os.path.isfile(dest)
        assert dest.endswith(".jpg")

    def test_rgba_to_jpg(self, tmp_path) -> None:
        src = tmp_path / "rgba.png"
        Image.new("RGBA", (50, 50), (255, 0, 0, 128)).save(str(src))

        dest = convert_image(str(src), ".jpg")
        assert os.path.isfile(dest)
        img = Image.open(dest)
        assert img.mode == "RGB"

    def test_palette_to_jpg(self, tmp_path) -> None:
        src = tmp_path / "palette.png"
        Image.new("P", (50, 50)).save(str(src))

        dest = convert_image(str(src), ".jpg")
        assert os.path.isfile(dest)
        img = Image.open(dest)
        assert img.mode == "RGB"

    def test_output_dir(self, tmp_path) -> None:
        src = tmp_path / "test.jpg"
        Image.new("RGB", (50, 50), "green").save(str(src))
        out_dir = tmp_path / "output"

        dest = convert_image(str(src), ".png", output_dir=str(out_dir))
        assert os.path.isfile(dest)
        assert str(out_dir) in dest

    def test_avoid_overwrite(self, tmp_path) -> None:
        src = tmp_path / "img.jpg"
        Image.new("RGB", (50, 50), "red").save(str(src))

        existing = tmp_path / "img.png"
        existing.write_text("existing")

        dest = convert_image(str(src), ".png")
        assert os.path.isfile(dest)
        assert "converted" in os.path.basename(dest)

    def test_ext_without_dot(self, tmp_path) -> None:
        src = tmp_path / "test.jpg"
        Image.new("RGB", (50, 50), "red").save(str(src))

        dest = convert_image(str(src), "png")
        assert dest.endswith(".png")

    def test_webp_quality(self, tmp_path) -> None:
        src = tmp_path / "test.jpg"
        Image.new("RGB", (50, 50), "red").save(str(src))

        dest = convert_image(str(src), ".webp")
        assert os.path.isfile(dest)
        assert dest.endswith(".webp")

    def test_tiff_compression(self, tmp_path) -> None:
        src = tmp_path / "test.jpg"
        Image.new("RGB", (50, 50), "red").save(str(src))

        dest = convert_image(str(src), ".tif")
        assert os.path.isfile(dest)

    def test_bmp_conversion(self, tmp_path) -> None:
        src = tmp_path / "test.png"
        Image.new("RGBA", (50, 50), (255, 0, 0, 128)).save(str(src))

        dest = convert_image(str(src), ".bmp")
        assert os.path.isfile(dest)
        img = Image.open(dest)
        assert img.mode == "RGB"

    def test_ico_conversion(self, tmp_path) -> None:
        src = tmp_path / "test.png"
        Image.new("RGBA", (32, 32), (0, 255, 0, 200)).save(str(src))

        dest = convert_image(str(src), ".ico")
        assert os.path.isfile(dest)


class TestConvertVideo:
    @patch("morphic.converter.converter._ffmpeg_available", return_value=False)
    def test_no_ffmpeg(self, mock_ffmpeg, tmp_path) -> None:
        src = tmp_path / "test.mp4"
        src.write_bytes(b"\x00" * 100)

        with pytest.raises(RuntimeError, match="ffmpeg is not installed"):
            convert_video(str(src), ".avi")

    @patch("morphic.converter.converter.subprocess.run")
    @patch("morphic.converter.converter._ffmpeg_available", return_value=True)
    def test_successful_conversion(
        self, mock_ffmpeg, mock_run, tmp_path
    ) -> None:
        src = tmp_path / "test.mp4"
        src.write_bytes(b"\x00" * 100)

        mock_run.return_value = MagicMock(returncode=0, stderr="")

        expected_dest = tmp_path / "test.avi"
        expected_dest.write_bytes(b"\x00" * 50)

        dest = convert_video(str(src), ".avi")
        assert dest.endswith(".avi")
        mock_run.assert_called_once()

    @patch("morphic.converter.converter.subprocess.run")
    @patch("morphic.converter.converter._ffmpeg_available", return_value=True)
    def test_ffmpeg_error(self, mock_ffmpeg, mock_run, tmp_path) -> None:
        src = tmp_path / "test.mp4"
        src.write_bytes(b"\x00" * 100)

        mock_run.return_value = MagicMock(
            returncode=1,
            stderr="conversion error",
        )

        with pytest.raises(RuntimeError, match="ffmpeg error"):
            convert_video(str(src), ".avi")

    @patch("morphic.converter.converter.subprocess.run")
    @patch("morphic.converter.converter._ffmpeg_available", return_value=True)
    def test_mkv_stream_copy(self, mock_ffmpeg, mock_run, tmp_path) -> None:
        src = tmp_path / "test.mp4"
        src.write_bytes(b"\x00" * 100)

        mock_run.return_value = MagicMock(returncode=0, stderr="")

        expected_dest = tmp_path / "test.mkv"
        expected_dest.write_bytes(b"\x00" * 50)

        dest = convert_video(str(src), ".mkv")
        assert dest.endswith(".mkv")
        cmd_args = mock_run.call_args[0][0]
        assert "-c" in cmd_args
        assert "copy" in cmd_args

    @patch("morphic.converter.converter.subprocess.run")
    @patch("morphic.converter.converter._ffmpeg_available", return_value=True)
    def test_ts_stream_copy(self, mock_ffmpeg, mock_run, tmp_path) -> None:
        src = tmp_path / "test.mp4"
        src.write_bytes(b"\x00" * 100)

        mock_run.return_value = MagicMock(returncode=0, stderr="")

        expected_dest = tmp_path / "test.ts"
        expected_dest.write_bytes(b"\x00" * 50)

        dest = convert_video(str(src), ".ts")
        assert dest.endswith(".ts")

    @patch("morphic.converter.converter.subprocess.run")
    @patch("morphic.converter.converter._ffmpeg_available", return_value=True)
    def test_output_dir(self, mock_ffmpeg, mock_run, tmp_path) -> None:
        src = tmp_path / "test.mp4"
        src.write_bytes(b"\x00" * 100)
        out_dir = tmp_path / "output"

        mock_run.return_value = MagicMock(returncode=0, stderr="")

        out_dir.mkdir()
        (out_dir / "test.avi").write_bytes(b"\x00" * 50)

        dest = convert_video(str(src), ".avi", output_dir=str(out_dir))
        assert str(out_dir) in dest

    @patch("morphic.converter.converter.subprocess.run")
    @patch("morphic.converter.converter._ffmpeg_available", return_value=True)
    def test_avoid_overwrite(self, mock_ffmpeg, mock_run, tmp_path) -> None:
        src = tmp_path / "test.mp4"
        src.write_bytes(b"\x00" * 100)

        existing = tmp_path / "test.avi"
        existing.write_bytes(b"\x00" * 50)

        mock_run.return_value = MagicMock(returncode=0, stderr="")

        dest = convert_video(str(src), ".avi")
        assert "converted" in os.path.basename(dest)


class TestConvertFile:
    def test_image_dispatch(self, tmp_path) -> None:
        src = tmp_path / "test.jpg"
        Image.new("RGB", (50, 50), "red").save(str(src))

        dest = convert_file(str(src), ".png")
        assert dest.endswith(".png")

    @patch("morphic.converter.converter.convert_video")
    def test_video_dispatch(self, mock_convert, tmp_path) -> None:
        src = tmp_path / "test.mp4"
        src.write_bytes(b"\x00" * 100)
        mock_convert.return_value = str(tmp_path / "test.avi")

        _ = convert_file(str(src), ".avi")
        mock_convert.assert_called_once()

    def test_unsupported_type(self, tmp_path) -> None:
        src = tmp_path / "test.txt"
        src.write_text("hello")

        with pytest.raises(ValueError, match="Unsupported"):
            convert_file(str(src), ".jpg")

    def test_ext_normalization(self, tmp_path) -> None:
        src = tmp_path / "test.jpeg"
        Image.new("RGB", (50, 50), "red").save(str(src), format="JPEG")

        dest = convert_file(str(src), "png")
        assert dest.endswith(".png")


class TestConvertHelperFunctions:
    def test_get_video_encoder_fallbacks(self, monkeypatch) -> None:
        monkeypatch.setattr(
            converter, "_is_torch_cuda_available", lambda: True
        )
        monkeypatch.setattr(converter, "_ffmpeg_has_hwaccel", lambda x: True)
        monkeypatch.setattr(
            converter, "_ffmpeg_has_encoder", lambda e: e == "h264_nvenc"
        )

        encoder, hw, out = converter._get_video_encoder(".mp4")
        assert encoder == "h264_nvenc"
        assert hw is True
        assert out == "mp4"

        monkeypatch.setattr(converter, "_ffmpeg_has_encoder", lambda e: False)
        encoder, hw, out = converter._get_video_encoder(".avi")
        assert encoder == "mpeg4"
        assert hw is False

        monkeypatch.setattr(
            converter,
            "_ffmpeg_has_encoder",
            lambda e: e in ("libsvtav1", "libaom-av1"),
        )
        encoder, hw, out = converter._get_video_encoder(".webm-av1")
        assert out == "webm"
        assert encoder in ("libsvtav1", "libaom-av1", "libvpx-vp9")

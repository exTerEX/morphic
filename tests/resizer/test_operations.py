"""Tests for morphic.resizer.operations."""

from __future__ import annotations

import os

import pytest
from PIL import Image

from morphic.resizer.operations import resize_image


def _make_image(path: str, size: tuple[int, int] = (200, 100)) -> str:
    Image.new("RGB", size, "blue").save(path)
    return path


class TestResizeModes:
    def test_fit(self, tmp_path) -> None:
        src = _make_image(str(tmp_path / "src.png"), (400, 200))
        dest = resize_image(
            src, 100, 100, mode="fit", output_folder=str(tmp_path / "out")
        )
        img = Image.open(dest)
        # fit keeps aspect ratio, so 100x50
        assert img.width <= 100
        assert img.height <= 100

    def test_fill(self, tmp_path) -> None:
        src = _make_image(str(tmp_path / "src.png"), (400, 200))
        dest = resize_image(
            src, 100, 100, mode="fill", output_folder=str(tmp_path / "out")
        )
        img = Image.open(dest)
        assert img.size == (100, 100)

    def test_stretch(self, tmp_path) -> None:
        src = _make_image(str(tmp_path / "src.png"), (400, 200))
        dest = resize_image(
            src, 100, 50, mode="stretch", output_folder=str(tmp_path / "out")
        )
        img = Image.open(dest)
        assert img.size == (100, 50)

    def test_pad(self, tmp_path) -> None:
        src = _make_image(str(tmp_path / "src.png"), (400, 200))
        dest = resize_image(
            src, 100, 100, mode="pad", output_folder=str(tmp_path / "out")
        )
        img = Image.open(dest)
        assert img.size == (100, 100)


class TestResizeErrors:
    def test_invalid_mode(self, tmp_path) -> None:
        src = _make_image(str(tmp_path / "src.png"))
        with pytest.raises(ValueError, match="Invalid mode"):
            resize_image(src, 100, 100, mode="bad")

    def test_nonexistent_file(self, tmp_path) -> None:
        with pytest.raises(FileNotFoundError):
            resize_image(str(tmp_path / "nope.png"), 100, 100)

    def test_zero_dimensions(self, tmp_path) -> None:
        src = _make_image(str(tmp_path / "src.png"))
        with pytest.raises(ValueError, match="positive"):
            resize_image(src, 0, 100)


class TestResizeOutput:
    def test_output_folder_created(self, tmp_path) -> None:
        src = _make_image(str(tmp_path / "src.png"))
        out = str(tmp_path / "new_dir")
        dest = resize_image(src, 50, 50, output_folder=out)
        assert os.path.isdir(out)
        assert os.path.isfile(dest)

    def test_format_override(self, tmp_path) -> None:
        src = _make_image(str(tmp_path / "src.png"))
        dest = resize_image(
            src,
            50,
            50,
            output_format=".jpg",
            output_folder=str(tmp_path / "out"),
        )
        assert dest.endswith(".jpg")
        img = Image.open(dest)
        assert img.mode == "RGB"

    def test_quality_param(self, tmp_path) -> None:
        src = _make_image(str(tmp_path / "src.jpg"))
        dest_high = resize_image(
            src, 50, 50, quality=95, output_folder=str(tmp_path / "hi")
        )
        dest_low = resize_image(
            src, 50, 50, quality=10, output_folder=str(tmp_path / "lo")
        )
        # Lower quality should be smaller file
        assert os.path.getsize(dest_low) <= os.path.getsize(dest_high)

    def test_rgba_to_jpg(self, tmp_path) -> None:
        src = str(tmp_path / "rgba.png")
        Image.new("RGBA", (50, 50), (255, 0, 0, 128)).save(src)
        dest = resize_image(
            src,
            30,
            30,
            output_format=".jpg",
            output_folder=str(tmp_path / "out"),
        )
        img = Image.open(dest)
        assert img.mode == "RGB"

    def test_palette_mode(self, tmp_path) -> None:
        src = str(tmp_path / "pal.png")
        Image.new("P", (50, 50)).save(src)
        dest = resize_image(src, 30, 30, output_folder=str(tmp_path / "out"))
        assert os.path.isfile(dest)

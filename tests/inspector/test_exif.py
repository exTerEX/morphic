"""Tests for morphic.inspector.exif."""

from __future__ import annotations


import pytest
from PIL import Image

from morphic.inspector.exif import (
    edit_exif,
    read_exif,
    strip_exif,
    strip_exif_batch,
)


def _make_jpeg(path: str, size: tuple[int, int] = (50, 50)) -> str:
    """Create a minimal JPEG file."""
    img = Image.new("RGB", size, "red")
    img.save(path, "JPEG")
    return path


class TestReadExif:
    def test_returns_dict(self, tmp_path) -> None:
        path = _make_jpeg(str(tmp_path / "photo.jpg"))
        result = read_exif(path)
        assert isinstance(result, dict)

    def test_nonexistent_file_raises(self, tmp_path) -> None:
        with pytest.raises((FileNotFoundError, Exception)):
            read_exif(str(tmp_path / "nope.jpg"))

    def test_png_returns_empty_or_dict(self, tmp_path) -> None:
        """PNG files may have no EXIF — should not crash."""
        p = tmp_path / "test.png"
        Image.new("RGB", (10, 10), "blue").save(str(p))
        result = read_exif(str(p))
        assert isinstance(result, dict)


class TestEditExif:
    def test_edit_roundtrip(self, tmp_path) -> None:
        path = _make_jpeg(str(tmp_path / "edit.jpg"))
        # Write some EXIF first so piexif can work with it
        edit_exif(path, {"ImageDescription": "hello world"})
        data = read_exif(path)
        assert data.get("ImageDescription") == "hello world"

    def test_edit_nonexistent_key_is_ignored(self, tmp_path) -> None:
        path = _make_jpeg(str(tmp_path / "edit2.jpg"))
        # Unknown key should be silently ignored
        edit_exif(path, {"TotallyFakeTag12345": "value"})


class TestStripExif:
    def test_strip_removes_data(self, tmp_path) -> None:
        path = _make_jpeg(str(tmp_path / "strip.jpg"))
        edit_exif(path, {"ImageDescription": "to be removed"})
        strip_exif(path)
        data = read_exif(path)
        assert data.get("ImageDescription") in (None, "")

    def test_strip_preserves_image(self, tmp_path) -> None:
        path = _make_jpeg(str(tmp_path / "strip2.jpg"))
        strip_exif(path)
        img = Image.open(path)
        assert img.size == (50, 50)


class TestStripExifBatch:
    def test_batch_returns_dict(self, tmp_path) -> None:
        paths = [_make_jpeg(str(tmp_path / f"img{i}.jpg")) for i in range(3)]
        results = strip_exif_batch(paths)
        assert isinstance(results, dict)
        assert len(results) == 3
        for path, info in results.items():
            assert "success" in info
            assert info["success"] is True

    def test_batch_with_bad_file(self, tmp_path) -> None:
        good = _make_jpeg(str(tmp_path / "good.jpg"))
        bad = str(tmp_path / "nonexistent.jpg")
        results = strip_exif_batch([good, bad])
        assert len(results) == 2
        assert results[good]["success"] is True
        assert results[bad]["success"] is False
        assert "error" in results[bad]

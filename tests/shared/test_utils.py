"""Tests for morphic.shared.utils."""

from __future__ import annotations

import os

from morphic.shared.utils import (
    find_files_by_extension,
    format_duration,
    format_file_size,
    is_excluded_path,
    is_image,
    is_video,
    normalise_ext,
    suppress_stderr,
)


class TestNormaliseExt:
    def test_jpeg_to_jpg(self) -> None:
        assert normalise_ext(".jpeg") == ".jpg"
        assert normalise_ext(".JPEG") == ".jpg"

    def test_tiff_to_tif(self) -> None:
        assert normalise_ext(".tiff") == ".tif"
        assert normalise_ext(".TIFF") == ".tif"

    def test_mpg_to_mpeg(self) -> None:
        assert normalise_ext(".mpg") == ".mpeg"

    def test_already_canonical(self) -> None:
        assert normalise_ext(".png") == ".png"
        assert normalise_ext(".mp4") == ".mp4"

    def test_case_insensitive(self) -> None:
        assert normalise_ext(".PNG") == ".png"
        assert normalise_ext(".Mp4") == ".mp4"

    def test_unknown_extension(self) -> None:
        assert normalise_ext(".xyz") == ".xyz"

    def test_empty_string(self) -> None:
        assert normalise_ext("") == ""


class TestIsImage:
    def test_common_image_extensions(self) -> None:
        for ext in ["jpg", "jpeg", "png", "tif", "tiff", "webp", "gif", "bmp"]:
            assert is_image(f"photo.{ext}"), f".{ext} should be image"

    def test_case_insensitive(self) -> None:
        assert is_image("photo.JPG")
        assert is_image("photo.Png")

    def test_not_image(self) -> None:
        assert not is_image("video.mp4")
        assert not is_image("document.pdf")
        assert not is_image("noext")

    def test_full_path(self) -> None:
        assert is_image("/home/user/photos/test.png")


class TestIsVideo:
    def test_common_video_extensions(self) -> None:
        for ext in ["mp4", "mov", "mkv", "avi", "webm"]:
            assert is_video(f"clip.{ext}"), f".{ext} should be video"

    def test_case_insensitive(self) -> None:
        assert is_video("clip.MP4")
        assert is_video("clip.Mov")

    def test_not_video(self) -> None:
        assert not is_video("photo.jpg")
        assert not is_video("document.pdf")

    def test_full_path(self) -> None:
        assert is_video("/home/user/videos/test.mp4")


class TestFormatFileSize:
    def test_bytes(self) -> None:
        assert format_file_size(512) == "512.00 B"

    def test_kilobytes(self) -> None:
        result = format_file_size(1536)
        assert "KB" in result

    def test_megabytes(self) -> None:
        result = format_file_size(2 * 1024 * 1024)
        assert "MB" in result

    def test_gigabytes(self) -> None:
        result = format_file_size(3 * 1024**3)
        assert "GB" in result

    def test_terabytes(self) -> None:
        result = format_file_size(2 * 1024**4)
        assert "TB" in result

    def test_zero(self) -> None:
        assert format_file_size(0) == "0.00 B"


class TestFormatDuration:
    def test_seconds_only(self) -> None:
        assert format_duration(45) == "45s"

    def test_minutes_and_seconds(self) -> None:
        assert format_duration(125) == "2m 5s"

    def test_hours_minutes_seconds(self) -> None:
        assert format_duration(3661) == "1h 1m 1s"

    def test_zero(self) -> None:
        assert format_duration(0) == "0s"


class TestIsExcludedPath:
    def test_excluded_folder(self) -> None:
        assert is_excluded_path("/home/user/node_modules/lib/file.jpg")

    def test_git_folder(self) -> None:
        assert is_excluded_path("/repo/.git/objects/file")

    def test_pycache(self) -> None:
        assert is_excluded_path("/project/__pycache__/module.pyc")

    def test_normal_path(self) -> None:
        assert not is_excluded_path("/home/user/photos/vacation.jpg")

    def test_custom_exclusions(self) -> None:
        assert is_excluded_path(
            "/project/custom/file.jpg",
            excluded_folders=frozenset({"custom"}),
        )


class TestFindFilesByExtension:
    def test_finds_images(self, tmp_path) -> None:
        (tmp_path / "a.jpg").touch()
        (tmp_path / "b.png").touch()
        (tmp_path / "c.txt").touch()

        result = find_files_by_extension(
            str(tmp_path),
            frozenset({".jpg", ".png"}),
        )
        assert len(result) == 2

    def test_recursive(self, tmp_path) -> None:
        (tmp_path / "a.jpg").touch()
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "b.jpg").touch()

        result = find_files_by_extension(
            str(tmp_path),
            frozenset({".jpg"}),
        )
        assert len(result) == 2

    def test_excludes_folders(self, tmp_path) -> None:
        (tmp_path / "a.jpg").touch()
        excluded = tmp_path / "node_modules"
        excluded.mkdir()
        (excluded / "b.jpg").touch()

        result = find_files_by_extension(
            str(tmp_path),
            frozenset({".jpg"}),
        )
        assert len(result) == 1

    def test_empty_folder(self, tmp_path) -> None:
        result = find_files_by_extension(
            str(tmp_path),
            frozenset({".jpg"}),
        )
        assert result == []

    def test_returns_sorted(self, tmp_path) -> None:
        (tmp_path / "c.jpg").touch()
        (tmp_path / "a.jpg").touch()
        (tmp_path / "b.jpg").touch()

        result = find_files_by_extension(
            str(tmp_path),
            frozenset({".jpg"}),
        )
        names = [os.path.basename(f) for f in result]
        assert names == sorted(names)


class TestSuppressStderr:
    def test_suppresses(self) -> None:
        import sys
        with suppress_stderr():
            sys.stderr.write("suppressed\n")

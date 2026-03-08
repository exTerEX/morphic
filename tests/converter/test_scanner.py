"""Tests for morphic.converter.scanner."""

from __future__ import annotations

import os

from morphic.converter.scanner import get_compatible_targets, scan_folder


class TestScanFolder:
    def test_empty_folder(self, tmp_path) -> None:
        result = scan_folder(str(tmp_path))
        assert result["total"] == 0
        assert result["files"] == []
        assert result["summary"] == {}

    def test_finds_image_files(self, tmp_media) -> None:
        result = scan_folder(str(tmp_media), filter_type="images")
        names = {f["name"] for f in result["files"]}
        assert "photo.jpg" in names
        assert "image.png" in names
        assert "pic.tif" in names
        assert "deep.jpg" in names
        assert result["total"] >= 4

    def test_finds_video_files(self, tmp_media) -> None:
        result = scan_folder(str(tmp_media), filter_type="videos")
        names = {f["name"] for f in result["files"]}
        assert "clip.mp4" in names
        assert "movie.mov" in names

    def test_filter_both(self, tmp_media) -> None:
        result = scan_folder(str(tmp_media), filter_type="both")
        types = {f["type"] for f in result["files"]}
        assert "image" in types
        assert "video" in types

    def test_no_subfolders(self, tmp_media) -> None:
        result = scan_folder(
            str(tmp_media), include_subfolders=False,
        )
        names = {f["name"] for f in result["files"]}
        assert "deep.jpg" not in names
        assert "photo.jpg" in names

    def test_with_subfolders(self, tmp_media) -> None:
        result = scan_folder(
            str(tmp_media), include_subfolders=True,
        )
        names = {f["name"] for f in result["files"]}
        assert "deep.jpg" in names

    def test_summary_counts(self, tmp_media) -> None:
        result = scan_folder(str(tmp_media), filter_type="images")
        assert ".jpg" in result["summary"]
        assert result["summary"][".jpg"] >= 2

    def test_files_have_required_keys(self, tmp_media) -> None:
        result = scan_folder(str(tmp_media))
        for f in result["files"]:
            assert "path" in f
            assert "name" in f
            assert "ext" in f
            assert "size" in f
            assert "type" in f
            assert "targets" in f

    def test_non_media_excluded(self, tmp_media) -> None:
        result = scan_folder(str(tmp_media))
        names = {f["name"] for f in result["files"]}
        assert "readme.txt" not in names

    def test_result_folder_matches(self, tmp_media) -> None:
        result = scan_folder(str(tmp_media))
        assert result["folder"] == str(tmp_media)


class TestGetCompatibleTargets:
    def test_jpg_targets(self) -> None:
        targets = get_compatible_targets("photo.jpg")
        assert ".png" in targets
        assert ".jpg" not in targets

    def test_mp4_targets(self) -> None:
        targets = get_compatible_targets("clip.mp4")
        assert ".mov" in targets or ".mkv" in targets

    def test_unknown_returns_empty(self) -> None:
        assert get_compatible_targets("file.xyz") == []

    def test_case_insensitive(self) -> None:
        targets = get_compatible_targets("photo.JPG")
        assert len(targets) > 0

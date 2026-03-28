"""Tests for morphic.converter.scanner."""

from __future__ import annotations

import pytest

from morphic.converter.scanner import get_compatible_targets, scan_folder


@pytest.mark.parametrize(
    "filter_type,expected_names",
    [
        (
            "images",
            {"photo.jpg", "image.png", "pic.tif", "deep.jpg"},
        ),
        ("videos", {"clip.mp4", "movie.mov"}),
    ],
)
def test_scan_folder_filter_types(
    tmp_media, filter_type, expected_names
) -> None:
    result = scan_folder(str(tmp_media), filter_type=filter_type)
    names = {f["name"] for f in result["files"]}
    assert expected_names <= names


def test_scan_folder_both_and_subfolder_control(tmp_media) -> None:
    both = scan_folder(str(tmp_media), filter_type="both")
    types = {f["type"] for f in both["files"]}
    assert "image" in types
    assert "video" in types

    without_sub = scan_folder(str(tmp_media), include_subfolders=False)
    names = {f["name"] for f in without_sub["files"]}
    assert "deep.jpg" not in names

    with_sub = scan_folder(str(tmp_media), include_subfolders=True)
    names = {f["name"] for f in with_sub["files"]}
    assert "deep.jpg" in names


def test_scan_folder_summary_and_meta(tmp_media) -> None:
    result = scan_folder(str(tmp_media), filter_type="images")
    assert ".jpg" in result["summary"]
    assert result["summary"][".jpg"] >= 2

    full = scan_folder(str(tmp_media))
    assert full["folder"] == str(tmp_media)
    for f in full["files"]:
        assert all(
            k in f for k in ["path", "name", "ext", "size", "type", "targets"]
        )
    names = {f["name"] for f in full["files"]}
    assert "readme.txt" not in names


@pytest.mark.parametrize(
    "filename,expected_substr",
    [
        ("photo.jpg", ".png"),
        ("clip.mp4", ".mov"),
        ("file.xyz", ""),
        ("photo.JPG", ""),
    ],
)
def test_compatible_targets(filename, expected_substr) -> None:
    targets = get_compatible_targets(filename)
    if expected_substr:
        assert expected_substr in targets
    else:
        if filename == "file.xyz":
            assert targets == []
        else:
            assert len(targets) > 0

"""Tests for morphic.converter.constants."""

from morphic.converter.constants import (
    IMAGE_CONVERSIONS,
    VIDEO_CONVERSIONS,
    _CANONICAL_IMAGE,
    _CANONICAL_VIDEO,
    _normalise,
)
from morphic.shared.constants import IMAGE_EXTENSIONS


class TestNormalise:
    def test_aliases(self) -> None:
        assert _normalise(".jpeg") == ".jpg"
        assert _normalise(".tiff") == ".tif"

    def test_passthrough(self) -> None:
        assert _normalise(".png") == ".png"

    def test_case_insensitive(self) -> None:
        assert _normalise(".JPEG") == ".jpg"


class TestCanonicalSets:
    def test_canonical_image_not_empty(self) -> None:
        assert len(_CANONICAL_IMAGE) > 0

    def test_canonical_video_not_empty(self) -> None:
        assert len(_CANONICAL_VIDEO) > 0

    def test_canonical_are_subsets(self) -> None:
        normed_img = {_normalise(e) for e in IMAGE_EXTENSIONS}
        for ext in _CANONICAL_IMAGE:
            assert ext in normed_img

    def test_common_image_canonicals(self) -> None:
        for ext in [".jpg", ".png", ".webp", ".bmp", ".gif"]:
            assert ext in _CANONICAL_IMAGE

    def test_common_video_canonicals(self) -> None:
        for ext in [".mp4", ".mov", ".avi", ".mkv", ".webm"]:
            assert ext in _CANONICAL_VIDEO


class TestImageConversions:
    def test_not_empty(self) -> None:
        assert len(IMAGE_CONVERSIONS) > 0

    def test_image_target_does_not_include_self(self) -> None:
        for ext, targets in IMAGE_CONVERSIONS.items():
            norm = _normalise(ext)
            assert norm not in targets, f"{norm} in targets for {ext}"

    def test_all_targets_are_canonical(self) -> None:
        for ext, targets in IMAGE_CONVERSIONS.items():
            for t in targets:
                assert t in _CANONICAL_IMAGE, f"{t} not canonical"

    def test_jpg_can_convert_to_png(self) -> None:
        targets = IMAGE_CONVERSIONS.get(".jpg", [])
        assert ".png" in targets

    def test_png_can_convert_to_jpg(self) -> None:
        targets = IMAGE_CONVERSIONS.get(".png", [])
        assert ".jpg" in targets

    def test_targets_are_sorted(self) -> None:
        for ext, targets in IMAGE_CONVERSIONS.items():
            assert targets == sorted(targets), f"targets for {ext} not sorted"


class TestVideoConversions:
    def test_not_empty(self) -> None:
        assert len(VIDEO_CONVERSIONS) > 0

    def test_video_target_does_not_include_self(self) -> None:
        for ext, targets in VIDEO_CONVERSIONS.items():
            norm = _normalise(ext)
            assert norm not in targets, f"{norm} in targets for {ext}"

    def test_all_targets_are_canonical(self) -> None:
        for ext, targets in VIDEO_CONVERSIONS.items():
            for t in targets:
                assert t in _CANONICAL_VIDEO, f"{t} not canonical"

    def test_mp4_can_convert_to_mkv(self) -> None:
        targets = VIDEO_CONVERSIONS.get(".mp4", [])
        assert ".mkv" in targets

    def test_targets_are_sorted(self) -> None:
        for ext, targets in VIDEO_CONVERSIONS.items():
            assert targets == sorted(targets), f"targets for {ext} not sorted"

"""Tests for morphic.shared.constants."""

from morphic.shared.constants import (
    ALIASES,
    ALL_EXTENSIONS,
    DEFAULT_BATCH_SIZE,
    DEFAULT_HASH_SIZE,
    DEFAULT_IMAGE_THRESHOLD,
    DEFAULT_NUM_FRAMES,
    DEFAULT_NUM_WORKERS,
    DEFAULT_VIDEO_THRESHOLD,
    EXCLUDED_FOLDERS,
    IMAGE_EXTENSIONS,
    VIDEO_EXTENSIONS,
)


class TestExtensionSets:
    def test_image_extensions_not_empty(self) -> None:
        assert len(IMAGE_EXTENSIONS) > 0

    def test_video_extensions_not_empty(self) -> None:
        assert len(VIDEO_EXTENSIONS) > 0

    def test_all_extensions_is_union(self) -> None:
        assert ALL_EXTENSIONS == IMAGE_EXTENSIONS | VIDEO_EXTENSIONS

    def test_no_overlap_between_image_and_video(self) -> None:
        assert IMAGE_EXTENSIONS & VIDEO_EXTENSIONS == set()

    def test_all_extensions_start_with_dot(self) -> None:
        for ext in ALL_EXTENSIONS:
            assert ext.startswith("."), f"{ext} missing leading dot"

    def test_extensions_are_lowercase(self) -> None:
        for ext in ALL_EXTENSIONS:
            assert ext == ext.lower(), f"{ext} not lowercase"

    def test_image_extensions_are_frozenset(self) -> None:
        assert isinstance(IMAGE_EXTENSIONS, frozenset)

    def test_video_extensions_are_frozenset(self) -> None:
        assert isinstance(VIDEO_EXTENSIONS, frozenset)

    def test_common_image_formats_present(self) -> None:
        for ext in [".jpg", ".png", ".gif", ".bmp", ".webp", ".tif"]:
            assert ext in IMAGE_EXTENSIONS

    def test_common_video_formats_present(self) -> None:
        for ext in [".mp4", ".mov", ".avi", ".mkv", ".webm"]:
            assert ext in VIDEO_EXTENSIONS


class TestAliases:
    def test_jpeg_alias(self) -> None:
        assert ALIASES[".jpeg"] == ".jpg"

    def test_tiff_alias(self) -> None:
        assert ALIASES[".tiff"] == ".tif"

    def test_mpg_alias(self) -> None:
        assert ALIASES[".mpg"] == ".mpeg"

    def test_aliases_are_lowercase(self) -> None:
        for key, val in ALIASES.items():
            assert key == key.lower()
            assert val == val.lower()


class TestExcludedFolders:
    def test_excluded_folders_not_empty(self) -> None:
        assert len(EXCLUDED_FOLDERS) > 0

    def test_common_exclusions_present(self) -> None:
        for name in ["node_modules", ".git", "__pycache__"]:
            assert name in EXCLUDED_FOLDERS

    def test_excluded_folders_are_frozenset(self) -> None:
        assert isinstance(EXCLUDED_FOLDERS, frozenset)


class TestDefaults:
    def test_image_threshold_range(self) -> None:
        assert 0 < DEFAULT_IMAGE_THRESHOLD <= 1.0

    def test_video_threshold_range(self) -> None:
        assert 0 < DEFAULT_VIDEO_THRESHOLD <= 1.0

    def test_hash_size_positive(self) -> None:
        assert DEFAULT_HASH_SIZE > 0

    def test_num_frames_positive(self) -> None:
        assert DEFAULT_NUM_FRAMES > 0

    def test_num_workers_positive(self) -> None:
        assert DEFAULT_NUM_WORKERS > 0

    def test_batch_size_positive(self) -> None:
        assert DEFAULT_BATCH_SIZE > 0

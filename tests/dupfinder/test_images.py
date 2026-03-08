"""Tests for morphic.dupfinder.images."""

from __future__ import annotations

import os
from unittest.mock import patch

import numpy as np
import pytest
from PIL import Image

from morphic.dupfinder.images import (
    ImageDuplicateFinder,
    ImageHasher,
    ImageInfo,
)


# ── ImageInfo ──────────────────────────────────────────────────────────────


class TestImageInfoToDict:
    def test_to_dict_keys(self) -> None:
        info = ImageInfo(
            path="/img.jpg", width=100, height=200,
            file_size=999, format="JPEG", mode="RGB",
            phash="abc", ahash="def", dhash="ghi",
        )
        d = info.to_dict()
        assert d["path"] == "/img.jpg"
        assert d["width"] == 100
        assert d["height"] == 200
        assert d["file_size"] == 999
        assert d["format"] == "JPEG"
        assert d["mode"] == "RGB"
        assert d["phash"] == "abc"
        assert d["ahash"] == "def"
        assert d["dhash"] == "ghi"

    def test_to_dict_none_hashes(self) -> None:
        info = ImageInfo(path="/x.jpg")
        d = info.to_dict()
        assert d["phash"] is None
        assert d["ahash"] is None
        assert d["dhash"] is None

    def test_defaults(self) -> None:
        info = ImageInfo(path="/test.jpg")
        assert info.path == "/test.jpg"
        assert info.width == 0
        assert info.height == 0
        assert info.file_size == 0
        assert info.phash is None

    def test_custom_values(self) -> None:
        info = ImageInfo(
            path="/a.jpg", width=1920, height=1080,
            format="JPEG", file_size=5000, phash="abc123",
        )
        assert info.width == 1920
        assert info.format == "JPEG"
        assert info.phash == "abc123"


# ── ImageHasher ────────────────────────────────────────────────────────────


class TestImageHasher:
    def test_default_hash_size(self) -> None:
        hasher = ImageHasher()
        assert hasher.hash_size == 16

    def test_custom_hash_size(self) -> None:
        hasher = ImageHasher(hash_size=8)
        assert hasher.hash_size == 8

    def test_compute_hashes_valid_image(self, tmp_path) -> None:
        img_path = tmp_path / "test.jpg"
        Image.new("RGB", (100, 100), "red").save(str(img_path))

        hasher = ImageHasher(hash_size=8)
        info = hasher.compute_hashes(str(img_path))

        assert info.path == str(img_path)
        assert info.width == 100
        assert info.height == 100
        assert info.file_size > 0
        assert info.format == "JPEG"
        assert info.mode == "RGB"
        assert info.phash is not None
        assert info.ahash is not None
        assert info.dhash is not None
        assert info.whash is not None

    def test_compute_hashes_rgba_image(self, tmp_path) -> None:
        img_path = tmp_path / "rgba.png"
        Image.new("RGBA", (50, 50), (255, 0, 0, 128)).save(str(img_path))

        hasher = ImageHasher(hash_size=8)
        info = hasher.compute_hashes(str(img_path))
        assert info.phash is not None

    def test_compute_hashes_palette_image(self, tmp_path) -> None:
        img_path = tmp_path / "palette.png"
        Image.new("P", (50, 50)).save(str(img_path))

        hasher = ImageHasher(hash_size=8)
        info = hasher.compute_hashes(str(img_path))
        assert info.phash is not None

    def test_compute_hashes_grayscale(self, tmp_path) -> None:
        img_path = tmp_path / "gray.png"
        Image.new("L", (50, 50), 128).save(str(img_path))

        hasher = ImageHasher(hash_size=8)
        info = hasher.compute_hashes(str(img_path))
        assert info.phash is not None
        assert info.mode == "L"

    def test_compute_hashes_nonexistent(self) -> None:
        hasher = ImageHasher(hash_size=8)
        info = hasher.compute_hashes("/nonexistent/file.jpg")
        assert info.phash is None
        assert info.file_size == 0

    def test_compute_hashes_corrupt_file(self, tmp_path) -> None:
        img_path = tmp_path / "corrupt.jpg"
        img_path.write_bytes(b"not an image")

        hasher = ImageHasher(hash_size=8)
        info = hasher.compute_hashes(str(img_path))
        assert info.phash is None

    def test_cmyk_image(self, tmp_path) -> None:
        img_path = tmp_path / "cmyk.jpg"
        img = Image.new("CMYK", (50, 50), (0, 0, 0, 0))
        img.save(str(img_path))

        hasher = ImageHasher(hash_size=8)
        info = hasher.compute_hashes(str(img_path))
        assert info.phash is not None


# ── ImageDuplicateFinder ───────────────────────────────────────────────────


class TestImageDuplicateFinder:
    def test_init_defaults(self) -> None:
        finder = ImageDuplicateFinder(use_gpu=False)
        assert finder.similarity_threshold == 0.90
        assert finder.hash_type == "combined"
        assert finder.use_gpu is False

    def test_find_images(self, tmp_path) -> None:
        (tmp_path / "a.jpg").write_bytes(b"\xff\xd8\xff\xe0")
        Image.new("RGB", (10, 10), "red").save(str(tmp_path / "b.png"))
        (tmp_path / "c.txt").write_text("hello")

        finder = ImageDuplicateFinder(use_gpu=False)
        files = finder.find_images(str(tmp_path))
        exts = {os.path.splitext(f)[1].lower() for f in files}
        assert ".txt" not in exts

    def test_process_images(self, tmp_path) -> None:
        for name in ["a.jpg", "b.jpg", "c.jpg"]:
            Image.new("RGB", (50, 50), "red").save(str(tmp_path / name))

        finder = ImageDuplicateFinder(use_gpu=False, hash_size=8)
        files = [str(tmp_path / n) for n in ["a.jpg", "b.jpg", "c.jpg"]]
        infos = finder.process_images(files)
        assert len(infos) == 3
        for info in infos.values():
            assert info.phash is not None

    def test_compute_similarity_identical(self, tmp_path) -> None:
        img_path = tmp_path / "test.jpg"
        Image.new("RGB", (50, 50), "red").save(str(img_path))

        finder = ImageDuplicateFinder(use_gpu=False, hash_size=8)
        info = finder.hasher.compute_hashes(str(img_path))
        similarity = finder.compute_similarity(info, info)
        assert similarity == pytest.approx(1.0)

    def test_compute_similarity_different(self, tmp_path) -> None:
        img1_path = tmp_path / "red.jpg"
        img2_path = tmp_path / "noise.jpg"
        Image.new("RGB", (50, 50), "red").save(str(img1_path))
        noise_arr = np.random.randint(0, 255, (50, 50, 3), dtype=np.uint8)
        Image.fromarray(noise_arr).save(str(img2_path))

        finder = ImageDuplicateFinder(use_gpu=False, hash_size=8)
        info1 = finder.hasher.compute_hashes(str(img1_path))
        info2 = finder.hasher.compute_hashes(str(img2_path))
        similarity = finder.compute_similarity(info1, info2)
        assert 0.0 <= similarity <= 1.0

    def test_compute_similarity_no_hashes(self) -> None:
        finder = ImageDuplicateFinder(use_gpu=False, hash_size=8)
        info1 = ImageInfo(path="/a.jpg")
        info2 = ImageInfo(path="/b.jpg")
        assert finder.compute_similarity(info1, info2) == 0.0

    def test_compute_similarity_phash_only(self, tmp_path) -> None:
        img_path = tmp_path / "test.jpg"
        Image.new("RGB", (50, 50), "red").save(str(img_path))

        finder = ImageDuplicateFinder(
            use_gpu=False, hash_size=8, hash_type="phash",
        )
        info = finder.hasher.compute_hashes(str(img_path))
        similarity = finder.compute_similarity(info, info)
        assert similarity == pytest.approx(1.0)

    def test_compute_similarity_ahash_only(self, tmp_path) -> None:
        img_path = tmp_path / "test.jpg"
        Image.new("RGB", (50, 50), "red").save(str(img_path))

        finder = ImageDuplicateFinder(
            use_gpu=False, hash_size=8, hash_type="ahash",
        )
        info = finder.hasher.compute_hashes(str(img_path))
        similarity = finder.compute_similarity(info, info)
        assert similarity == pytest.approx(1.0)

    def test_compute_similarity_dhash_only(self, tmp_path) -> None:
        img_path = tmp_path / "test.jpg"
        Image.new("RGB", (50, 50), "red").save(str(img_path))

        finder = ImageDuplicateFinder(
            use_gpu=False, hash_size=8, hash_type="dhash",
        )
        info = finder.hasher.compute_hashes(str(img_path))
        similarity = finder.compute_similarity(info, info)
        assert similarity == pytest.approx(1.0)

    def test_compute_similarity_whash_only(self, tmp_path) -> None:
        img_path = tmp_path / "test.jpg"
        Image.new("RGB", (50, 50), "red").save(str(img_path))

        finder = ImageDuplicateFinder(
            use_gpu=False, hash_size=8, hash_type="whash",
        )
        info = finder.hasher.compute_hashes(str(img_path))
        similarity = finder.compute_similarity(info, info)
        assert similarity == pytest.approx(1.0)

    def test_find_duplicates_identical_images(self, tmp_path) -> None:
        for name in ["a.jpg", "b.jpg", "c.jpg"]:
            Image.new("RGB", (50, 50), "red").save(str(tmp_path / name))

        finder = ImageDuplicateFinder(
            use_gpu=False, hash_size=8, similarity_threshold=0.9,
        )
        files = [str(tmp_path / n) for n in ["a.jpg", "b.jpg", "c.jpg"]]
        finder.process_images(files)
        groups = finder.find_duplicates()
        assert len(groups) >= 1

    def test_find_duplicates_fast_identical(self, tmp_path) -> None:
        for name in ["a.jpg", "b.jpg"]:
            Image.new("RGB", (50, 50), "red").save(str(tmp_path / name))

        finder = ImageDuplicateFinder(
            use_gpu=False, hash_size=8, similarity_threshold=0.9,
        )
        files = [str(tmp_path / n) for n in ["a.jpg", "b.jpg"]]
        finder.process_images(files)
        groups = finder.find_duplicates_fast()
        assert len(groups) >= 1

    def test_find_duplicates_no_images(self) -> None:
        finder = ImageDuplicateFinder(use_gpu=False, hash_size=8)
        groups = finder.find_duplicates()
        assert groups == []

    def test_find_near_duplicates_empty(self) -> None:
        finder = ImageDuplicateFinder(use_gpu=False, hash_size=8)
        groups = finder._find_near_duplicates([])
        assert groups == []

    def test_find_duplicates_fast_with_near_dups(self, tmp_path) -> None:
        img1_path = tmp_path / "a.jpg"
        img2_path = tmp_path / "b.jpg"

        arr = np.ones((50, 50, 3), dtype=np.uint8) * 128
        Image.fromarray(arr).save(str(img1_path))
        arr[25, 25] = [255, 0, 0]
        Image.fromarray(arr).save(str(img2_path))

        finder = ImageDuplicateFinder(
            use_gpu=False, hash_size=8, similarity_threshold=0.8,
        )
        files = [str(img1_path), str(img2_path)]
        finder.process_images(files)
        groups = finder.find_duplicates_fast()
        assert isinstance(groups, list)

    @patch("morphic.dupfinder.images._compute_similarity_matrix_gpu")
    @patch("morphic.dupfinder.images._gpu_available", True)
    def test_find_near_duplicates_gpu(self, mock_sim, tmp_path) -> None:
        for name in ["a.jpg", "b.jpg", "c.jpg"]:
            Image.new("RGB", (50, 50), "red").save(str(tmp_path / name))

        finder = ImageDuplicateFinder(
            use_gpu=False, hash_size=8, similarity_threshold=0.9,
        )
        files = [str(tmp_path / n) for n in ["a.jpg", "b.jpg", "c.jpg"]]
        finder.process_images(files)
        finder.use_gpu = True

        n = len(finder.image_infos)
        sim_matrix = np.ones((n, n), dtype=np.float32)
        mock_sim.return_value = sim_matrix

        paths = list(finder.image_infos.keys())
        result = finder._find_near_duplicates_gpu(paths)
        assert isinstance(result, list)

    @patch("morphic.dupfinder.images._compute_similarity_matrix_gpu")
    @patch("morphic.dupfinder.images._gpu_available", True)
    def test_find_near_duplicates_gpu_fallback(self, mock_sim, tmp_path) -> None:
        for name in ["a.jpg", "b.jpg"]:
            Image.new("RGB", (50, 50), "red").save(str(tmp_path / name))

        finder = ImageDuplicateFinder(
            use_gpu=False, hash_size=8, similarity_threshold=0.9,
        )
        files = [str(tmp_path / n) for n in ["a.jpg", "b.jpg"]]
        finder.process_images(files)
        finder.use_gpu = True

        mock_sim.side_effect = RuntimeError("GPU failed")
        paths = list(finder.image_infos.keys())
        result = finder._find_near_duplicates_gpu(paths)
        assert isinstance(result, list)

    def test_find_near_duplicates_gpu_empty(self) -> None:
        finder = ImageDuplicateFinder(use_gpu=False, hash_size=8)
        result = finder._find_near_duplicates_gpu([])
        assert result == []

    def test_find_duplicates_uses_fast_for_large(self, tmp_path) -> None:
        finder = ImageDuplicateFinder(use_gpu=False, hash_size=8)
        for i in range(105):
            path = f"/fake/img_{i}.jpg"
            finder.image_infos[path] = ImageInfo(
                path=path, phash=f"hash{i:04d}",
                ahash=f"ahash{i:04d}", dhash=f"dhash{i:04d}",
            )

        with patch.object(finder, "find_duplicates_fast", return_value=[]) as mock:
            finder.find_duplicates()
            mock.assert_called_once()

    def test_find_duplicates_regular_path(self, tmp_path) -> None:
        for name in ["a.jpg", "b.jpg"]:
            Image.new("RGB", (50, 50), "red").save(str(tmp_path / name))

        finder = ImageDuplicateFinder(
            use_gpu=False, hash_size=8, similarity_threshold=0.9,
        )
        files = [str(tmp_path / n) for n in ["a.jpg", "b.jpg"]]
        finder.process_images(files)
        groups = finder.find_duplicates()
        assert isinstance(groups, list)

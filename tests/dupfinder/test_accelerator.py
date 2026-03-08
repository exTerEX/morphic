"""Tests for morphic.dupfinder.accelerator."""

from __future__ import annotations

from typing import cast
from unittest.mock import patch

import numpy as np
import pytest

from morphic.dupfinder.accelerator import (
    AcceleratorType,
    GPUAccelerator,
    compute_phash_gpu,
    compute_similarity_matrix_gpu,
    get_accelerator,
)


class TestGPUAcceleratorProperties:
    def test_is_gpu_available_on_cpu(self) -> None:
        acc = GPUAccelerator()
        if acc.backend == AcceleratorType.CPU:
            assert acc.is_gpu_available is False
        else:
            assert acc.is_gpu_available is True

    def test_get_backend_name(self) -> None:
        acc = GPUAccelerator()
        name = acc.get_backend_name()
        assert isinstance(name, str)
        assert len(name) > 0
        expected = {
            "CUDA (NVIDIA GPU)", "ROCm (AMD GPU)",
            "OpenCL (GPU)", "CPU Multiprocessing",
        }
        assert name in expected

    def test_num_cpus(self) -> None:
        acc = GPUAccelerator()
        assert acc.num_cpus >= 1


class TestResizeImageBatch:
    def test_empty_batch(self) -> None:
        acc = GPUAccelerator()
        result = acc.resize_image_batch([], (32, 32))
        assert result == []

    def test_single_image(self) -> None:
        acc = GPUAccelerator()
        img = np.random.randint(0, 255, (100, 80, 3), dtype=np.uint8)
        result = acc.resize_image_batch([img], (32, 32))
        assert len(result) == 1
        assert result[0].shape[0] == 32
        assert result[0].shape[1] == 32

    def test_multiple_images(self) -> None:
        acc = GPUAccelerator()
        imgs = [
            np.random.randint(0, 255, (100, 80, 3), dtype=np.uint8)
            for _ in range(3)
        ]
        result = acc.resize_image_batch(imgs, (64, 64))
        assert len(result) == 3
        for r in result:
            assert r.shape[:2] == (64, 64)

    def test_grayscale_image(self) -> None:
        acc = GPUAccelerator()
        img = np.random.randint(0, 255, (100, 80), dtype=np.uint8)
        result = acc.resize_image_batch([img], (32, 32))
        assert len(result) == 1


class TestComputeDctBatch:
    def test_single_image(self) -> None:
        acc = GPUAccelerator()
        img = np.random.rand(32, 32).astype(np.float32)
        result = acc.compute_dct_batch([img])
        assert len(result) == 1
        assert result[0].shape == (32, 32)

    def test_multiple_images(self) -> None:
        acc = GPUAccelerator()
        imgs = [np.random.rand(16, 16).astype(np.float32) for _ in range(3)]
        result = acc.compute_dct_batch(imgs)
        assert len(result) == 3


class TestComputeSimilarityMatrix:
    def test_empty_hashes(self) -> None:
        acc = GPUAccelerator()
        result = acc.compute_similarity_matrix([])
        assert result.size == 0

    def test_identical_hashes(self) -> None:
        acc = GPUAccelerator()
        h = np.array([1, 0, 1, 0, 1, 0, 1, 0], dtype=np.float32)
        result = acc.compute_similarity_matrix([h, h])
        assert result.shape == (2, 2)
        assert result[0, 1] == pytest.approx(1.0)
        assert result[1, 0] == pytest.approx(1.0)

    def test_different_hashes(self) -> None:
        acc = GPUAccelerator()
        h1 = np.array([1, 0, 1, 0, 1, 0, 1, 0], dtype=np.float32)
        h2 = np.array([0, 1, 0, 1, 0, 1, 0, 1], dtype=np.float32)
        result = acc.compute_similarity_matrix([h1, h2])
        assert result.shape == (2, 2)
        assert result[0, 1] < 0.5


class TestBatchHammingDistance:
    def test_identical_hashes(self) -> None:
        acc = GPUAccelerator()
        hashes = ["abcdef01", "abcdef01"]
        result = acc.batch_hamming_distance(hashes, hashes)
        assert result.shape == (2, 2)
        assert result[0, 0] == pytest.approx(0.0)
        assert result[1, 1] == pytest.approx(0.0)

    def test_different_hashes(self) -> None:
        acc = GPUAccelerator()
        h1 = ["ff000000"]
        h2 = ["00ffffff"]
        result = acc.batch_hamming_distance(h1, h2)
        assert result.shape == (1, 1)
        assert result[0, 0] > 0


class TestGetAccelerator:
    def test_returns_gpu_accelerator(self) -> None:
        acc = get_accelerator()
        assert isinstance(acc, GPUAccelerator)

    def test_returns_same_instance(self) -> None:
        a1 = get_accelerator()
        a2 = get_accelerator()
        assert a1 is a2


class TestComputePhashGpu:
    def test_empty_list(self) -> None:
        result = compute_phash_gpu([])
        assert result == []

    def test_single_image(self) -> None:
        img = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        result = compute_phash_gpu([img], hash_size=8)
        assert len(result) == 1
        assert isinstance(result[0], np.ndarray)

    def test_grayscale_image(self) -> None:
        img = np.random.randint(0, 255, (100, 100), dtype=np.uint8)
        result = compute_phash_gpu([img], hash_size=8)
        assert len(result) == 1


class TestComputeSimilarityMatrixGpu:
    def test_empty(self) -> None:
        result = compute_similarity_matrix_gpu([])
        assert result.size == 0

    def test_hex_strings(self) -> None:
        hashes = ["abcdef0123456789", "abcdef0123456789"]
        result = compute_similarity_matrix_gpu(cast(list[str | np.ndarray], hashes), hash_size=4)
        assert result.shape == (2, 2)
        assert result[0, 1] == pytest.approx(1.0)

    def test_numpy_arrays(self) -> None:
        h1 = np.array([1, 0, 1, 0], dtype=np.uint8)
        h2 = np.array([1, 0, 1, 0], dtype=np.uint8)
        result = compute_similarity_matrix_gpu([h1, h2], hash_size=2)
        assert result.shape == (2, 2)

    def test_invalid_hex_string(self) -> None:
        """Non-hex strings should trigger ValueError and return zeros."""
        result = compute_similarity_matrix_gpu(["gg", "hh"], hash_size=2)
        assert result.shape == (2, 2)

    def test_all_invalid_hex(self) -> None:
        """All invalid hex strings should all map to zeros."""
        result = compute_similarity_matrix_gpu(["zz", "xx"], hash_size=2)
        assert result.shape == (2, 2)


class TestAcceleratorCPUMethods:
    def test_resize_batch_cpu_grayscale(self) -> None:
        acc = GPUAccelerator()
        img = np.random.randint(0, 255, (100, 80), dtype=np.uint8)
        result = acc._resize_batch_cpu([img], (32, 32))
        assert len(result) == 1

    def test_dct_batch_cpu_multiple(self) -> None:
        acc = GPUAccelerator()
        imgs = [np.random.rand(16, 16).astype(np.float32) for _ in range(5)]
        result = acc._dct_batch_cpu(imgs)
        assert len(result) == 5

    def test_similarity_matrix_cpu(self) -> None:
        acc = GPUAccelerator()
        h1 = np.array([1, 0, 1, 0, 1, 0, 1, 0], dtype=np.float32)
        h2 = np.array([0, 1, 0, 1, 0, 1, 0, 1], dtype=np.float32)
        matrix = np.vstack([h1, h2])
        result = acc._similarity_matrix_cpu(matrix, 2)
        assert result.shape == (2, 2)

    def test_batch_hamming_cpu(self) -> None:
        acc = GPUAccelerator()
        arr1 = np.array([[1, 0, 1, 0]], dtype=np.float32)
        arr2 = np.array([[1, 0, 1, 0]], dtype=np.float32)
        result = acc._batch_hamming_cpu(arr1, arr2)
        assert result.shape == (1, 1)
        assert result[0, 0] == pytest.approx(0.0)


class TestAcceleratorTorchPath:
    def test_try_cuda_no_torch(self) -> None:
        acc = GPUAccelerator()
        original_backend = acc.backend
        with patch.dict("sys.modules", {"torch": None}):
            result = acc._try_cuda()
            assert isinstance(result, bool)
        acc.backend = original_backend

    def test_try_rocm_no_torch(self) -> None:
        acc = GPUAccelerator()
        with patch.dict("sys.modules", {"torch": None}):
            result = acc._try_rocm()
            assert result is False

    def test_try_opencl_no_pyopencl(self) -> None:
        acc = GPUAccelerator()
        with patch.dict("sys.modules", {"pyopencl": None}):
            result = acc._try_opencl()
            assert result is False

    def test_setup_cpu(self) -> None:
        acc = GPUAccelerator()
        acc._setup_cpu()
        assert acc.backend == AcceleratorType.CPU


class TestAcceleratorBranchSelection:
    def test_resize_routes_to_cpu_when_cpu_backend(self) -> None:
        acc = GPUAccelerator()
        original = acc.backend
        acc.backend = AcceleratorType.CPU
        acc._torch = None
        acc._cp = None

        img = np.random.randint(0, 255, (50, 50, 3), dtype=np.uint8)
        result = acc.resize_image_batch([img], (16, 16))
        assert len(result) == 1

        acc.backend = original

    def test_dct_routes_to_cpu_when_cpu_backend(self) -> None:
        acc = GPUAccelerator()
        original = acc.backend
        acc.backend = AcceleratorType.CPU
        acc._torch = None
        acc._cp = None

        img = np.random.rand(16, 16).astype(np.float32)
        result = acc.compute_dct_batch([img])
        assert len(result) == 1

        acc.backend = original

    def test_similarity_routes_to_cpu_when_cpu_backend(self) -> None:
        acc = GPUAccelerator()
        original = acc.backend
        acc.backend = AcceleratorType.CPU
        acc._torch = None
        acc._cp = None

        h = np.array([1, 0, 1, 0], dtype=np.float32)
        result = acc.compute_similarity_matrix([h, h])
        assert result.shape == (2, 2)

        acc.backend = original

    def test_hamming_routes_to_cpu_when_cpu_backend(self) -> None:
        acc = GPUAccelerator()
        original = acc.backend
        acc.backend = AcceleratorType.CPU
        acc._torch = None
        acc._cp = None

        result = acc.batch_hamming_distance(["abcd"], ["abcd"])
        assert result.shape == (1, 1)

        acc.backend = original

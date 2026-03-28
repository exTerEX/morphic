"""
GPU Accelerator Module

Provides GPU-accelerated operations for image/video processing with automatic
fallback through: CUDA -> AMD/ROCm -> OpenCL -> CPU multiprocessing

Accelerates:
1. Image resizing/preprocessing
2. DCT computation for perceptual hashing
3. Hamming distance computation for similarity matrix
"""

from __future__ import annotations

import importlib
import logging
import multiprocessing as mp
import warnings
from enum import Enum, auto
from typing import Any, Sequence

import numpy as np

# Suppress PyTorch CUDA capability warnings during detection
warnings.filterwarnings("ignore", message=".*CUDA capability.*")
warnings.filterwarnings("ignore", message=".*cuda capability.*")
warnings.filterwarnings("ignore", message=".*Please install PyTorch.*")

logger = logging.getLogger(__name__)


class AcceleratorType(Enum):
    """Available acceleration backends."""

    CUDA = auto()
    ROCM = auto()
    OPENCL = auto()
    CPU = auto()


class GPUAccelerator:
    """
    GPU-accelerated operations with automatic backend detection and fallback.

    Priority: CUDA -> ROCm -> OpenCL -> CPU multiprocessing
    """

    _instance: GPUAccelerator | None = None
    _initialized: bool = False

    def __new__(cls) -> GPUAccelerator:
        """Singleton pattern to avoid multiple GPU initializations."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return

        self.backend: AcceleratorType = AcceleratorType.CPU
        self.device = None
        self.torch_device = None
        self._torch: Any = None
        self._cp: Any = None
        self._cl: Any = None
        self._cl_ctx: Any = None
        self._cl_queue: Any = None
        self.num_cpus = mp.cpu_count()

        self._detect_backend()
        self._initialized = True

    def _detect_backend(self) -> None:
        """Detect available GPU backend with priority fallback."""
        if self._try_cuda():
            return  # pragma: no cover
        if self._try_rocm():
            return  # pragma: no cover
        if self._try_opencl():
            return  # pragma: no cover
        self._setup_cpu()

    def _try_cuda(self) -> bool:  # pragma: no cover
        """Try to initialize CUDA backend."""
        try:
            torch = importlib.import_module("torch")
            if (
                getattr(torch, "cuda", None) is not None
                and torch.cuda.is_available()
            ):
                try:
                    test_device = torch.device("cuda")
                    test_tensor = torch.zeros(1, device=test_device)
                    _ = test_tensor + 1
                    del test_tensor
                    torch.cuda.empty_cache()

                    self._torch = torch
                    self.torch_device = test_device
                    self.backend = AcceleratorType.CUDA
                    gpu_name = torch.cuda.get_device_name(0)
                    logger.info(
                        "Using CUDA acceleration via PyTorch: %s",
                        gpu_name,
                    )
                    return True
                except RuntimeError as e:
                    logger.warning(
                        "PyTorch CUDA available but not functional: %s",
                        e,
                    )
        except (ImportError, Exception):
            pass

        try:
            cp = importlib.import_module("cupy")
            if getattr(cp, "cuda", None) is not None:
                device_count = cp.cuda.runtime.getDeviceCount()
                if device_count > 0:
                    test_arr = cp.zeros(1)
                    _ = test_arr + 1
                    del test_arr
                    cp.get_default_memory_pool().free_all_blocks()

                    self._cp = cp
                    self.backend = AcceleratorType.CUDA
                    device_props = cp.cuda.runtime.getDeviceProperties(0)
                    gpu_name = (
                        device_props["name"].decode()
                        if isinstance(device_props["name"], bytes)
                        else device_props["name"]
                    )
                    logger.info(
                        "Using CUDA acceleration via CuPy: %s",
                        gpu_name,
                    )
                    return True
        except (ImportError, Exception) as e:
            logger.debug("CuPy CUDA not available: %s", e)

        return False

    def _try_rocm(self) -> bool:  # pragma: no cover
        """Try to initialize AMD ROCm backend via PyTorch."""
        try:
            torch = importlib.import_module("torch")

            if (
                getattr(torch, "cuda", None) is not None
                and torch.cuda.is_available()
            ):
                return False

            if (
                hasattr(torch, "hip")
                and getattr(torch.hip, "is_available", lambda: False)()
            ):
                self._torch = torch
                self.torch_device = torch.device("cuda")
                self.backend = AcceleratorType.ROCM
                logger.info("Using AMD ROCm acceleration via PyTorch")
                return True
        except (ImportError, AttributeError):
            pass
        return False

    def _try_opencl(self) -> bool:  # pragma: no cover
        """Try to initialize OpenCL backend."""
        try:
            cl = importlib.import_module("pyopencl")

            try:
                platforms = cl.get_platforms()
            except Exception as e:
                logger.debug("OpenCL platform enumeration failed: %s", e)
                return False

            if not platforms:
                return False

            for platform in platforms:
                try:
                    devices = platform.get_devices(
                        device_type=cl.device_type.GPU,
                    )
                    if devices:
                        self._cl = cl
                        self._cl_ctx = cl.Context(devices=[devices[0]])
                        self._cl_queue = cl.CommandQueue(self._cl_ctx)
                        self.backend = AcceleratorType.OPENCL
                        logger.info(
                            "Using OpenCL acceleration: %s",
                            devices[0].name,
                        )
                        return True
                except Exception:
                    continue
        except ImportError:
            pass
        return False

    def _setup_cpu(self) -> None:
        """Set up CPU multiprocessing backend."""
        self.backend = AcceleratorType.CPU
        logger.info(
            "Using CPU multiprocessing with %d cores",
            self.num_cpus,
        )

    @property
    def is_gpu_available(self) -> bool:
        """Check if any GPU acceleration is available."""
        return self.backend in (
            AcceleratorType.CUDA,
            AcceleratorType.ROCM,
            AcceleratorType.OPENCL,
        )

    def get_backend_name(self) -> str:
        """Get human-readable backend name."""
        names = {
            AcceleratorType.CUDA: "CUDA (NVIDIA GPU)",
            AcceleratorType.ROCM: "ROCm (AMD GPU)",
            AcceleratorType.OPENCL: "OpenCL (GPU)",
            AcceleratorType.CPU: "CPU Multiprocessing",
        }
        return names.get(self.backend, "Unknown")

    # ── Batch operations ───────────────────────────────────────────────

    def resize_image_batch(
        self,
        images: list[np.ndarray],
        target_size: tuple[int, int],
    ) -> list[np.ndarray]:
        """Resize a batch of images using the best available backend."""
        if not images:
            return []
        if (
            self.backend == AcceleratorType.CUDA and self._torch is not None
        ):  # pragma: no cover
            return self._resize_batch_torch(
                images, target_size
            )  # pragma: no cover
        if (
            self.backend == AcceleratorType.CUDA and self._cp is not None
        ):  # pragma: no cover
            return self._resize_batch_cupy(
                images, target_size
            )  # pragma: no cover
        return self._resize_batch_cpu(images, target_size)

    def _resize_batch_torch(  # pragma: no cover
        self,
        images: list[np.ndarray],
        target_size: tuple[int, int],
    ) -> list[np.ndarray]:
        torch_nn_functional = importlib.import_module("torch.nn.functional")
        functional = torch_nn_functional

        assert self._torch is not None
        results = []
        target_h, target_w = target_size[1], target_size[0]
        for img in images:
            if len(img.shape) == 2:
                img = img[:, :, np.newaxis]
            tensor = (
                self._torch.from_numpy(img)
                .float()
                .permute(2, 0, 1)
                .unsqueeze(0)
                .to(self.torch_device)
            )
            resized = functional.interpolate(
                tensor,
                size=(target_h, target_w),
                mode="bilinear",
                align_corners=False,
            )
            result = (
                resized.squeeze(0)
                .permute(1, 2, 0)
                .cpu()
                .numpy()
                .astype(np.uint8)
            )
            if result.shape[2] == 1:
                result = result.squeeze(2)
            results.append(result)
        return results

    def _resize_batch_cupy(  # pragma: no cover
        self,
        images: list[np.ndarray],
        target_size: tuple[int, int],
    ) -> list[np.ndarray]:
        cupyx_ndimage = importlib.import_module("cupyx.scipy.ndimage")
        zoom = getattr(cupyx_ndimage, "zoom")

        assert self._cp is not None
        results = []
        for img in images:
            if len(img.shape) == 2:
                zoom_factors = (
                    target_size[1] / img.shape[0],
                    target_size[0] / img.shape[1],
                )
            else:
                zoom_factors = (
                    target_size[1] / img.shape[0],
                    target_size[0] / img.shape[1],
                    1,
                )
            gpu_img = self._cp.asarray(img)
            resized = zoom(gpu_img, zoom_factors, order=1)
            results.append(self._cp.asnumpy(resized).astype(np.uint8))
        return results

    def _resize_batch_cpu(
        self,
        images: list[np.ndarray],
        target_size: tuple[int, int],
    ) -> list[np.ndarray]:
        import cv2

        return [
            cv2.resize(img, target_size, interpolation=cv2.INTER_LINEAR)
            for img in images
        ]

    def compute_dct_batch(
        self,
        images: list[np.ndarray],
    ) -> list[np.ndarray]:
        """Compute DCT for a batch of images (used in pHash)."""
        if (
            self.backend == AcceleratorType.CUDA and self._torch is not None
        ):  # pragma: no cover
            return self._dct_batch_torch(images)  # pragma: no cover
        if (
            self.backend == AcceleratorType.CUDA and self._cp is not None
        ):  # pragma: no cover
            return self._dct_batch_cupy(images)  # pragma: no cover
        return self._dct_batch_cpu(images)

    def _dct_batch_torch(  # pragma: no cover
        self,
        images: list[np.ndarray],
    ) -> list[np.ndarray]:
        results = []
        for img in images:
            tensor = self._torch.from_numpy(img.astype(np.float32)).to(
                self.torch_device
            )
            dct = self._torch.fft.fft2(tensor).real
            results.append(dct.cpu().numpy())
        return results

    def _dct_batch_cupy(  # pragma: no cover
        self,
        images: list[np.ndarray],
    ) -> list[np.ndarray]:
        results = []
        for img in images:
            gpu_img = self._cp.asarray(img.astype(np.float32))
            dct = self._cp.fft.fft2(gpu_img).real
            results.append(self._cp.asnumpy(dct))
        return results

    def _dct_batch_cpu(
        self,
        images: list[np.ndarray],
    ) -> list[np.ndarray]:
        from scipy.fftpack import dct

        results = []
        for img in images:
            dct_result = dct(
                dct(img.astype(np.float32).T, norm="ortho").T,
                norm="ortho",
            )
            results.append(dct_result)
        return results

    def compute_similarity_matrix(
        self,
        hashes: list[np.ndarray],
        threshold: float = 0.0,
    ) -> np.ndarray:
        """Compute pairwise similarity matrix for hash arrays."""
        if not hashes:
            return np.array([])

        n = len(hashes)
        hash_matrix = np.vstack(
            [h.flatten() for h in hashes],
        ).astype(np.float32)

        if (
            self.backend == AcceleratorType.CUDA and self._torch is not None
        ):  # pragma: no cover
            return self._similarity_matrix_torch(
                hash_matrix, n
            )  # pragma: no cover
        if (
            self.backend == AcceleratorType.CUDA and self._cp is not None
        ):  # pragma: no cover
            return self._similarity_matrix_cupy(
                hash_matrix, n
            )  # pragma: no cover
        return self._similarity_matrix_cpu(hash_matrix, n)

    def _similarity_matrix_torch(  # pragma: no cover
        self,
        hash_matrix: np.ndarray,
        n: int,
    ) -> np.ndarray:
        gpu_hashes = self._torch.from_numpy(hash_matrix).to(self.torch_device)
        h1 = gpu_hashes.unsqueeze(1)
        h2 = gpu_hashes.unsqueeze(0)
        diff = (h1 != h2).float().sum(dim=2)
        max_dist = hash_matrix.shape[1]
        similarity = 1.0 - (diff / max_dist)
        return similarity.cpu().numpy()

    def _similarity_matrix_cupy(  # pragma: no cover
        self,
        hash_matrix: np.ndarray,
        n: int,
    ) -> np.ndarray:
        gpu_hashes = self._cp.asarray(hash_matrix)
        h1 = gpu_hashes[:, self._cp.newaxis, :]
        h2 = gpu_hashes[self._cp.newaxis, :, :]
        diff = self._cp.sum(h1 != h2, axis=2).astype(self._cp.float32)
        max_dist = hash_matrix.shape[1]
        similarity = 1.0 - (diff / max_dist)
        return self._cp.asnumpy(similarity)

    def _similarity_matrix_cpu(
        self,
        hash_matrix: np.ndarray,
        n: int,
    ) -> np.ndarray:
        from scipy.spatial.distance import cdist

        distances = cdist(hash_matrix, hash_matrix, metric="hamming")
        return (1.0 - distances).astype(np.float32)

    def batch_hamming_distance(
        self,
        hashes1: list[str],
        hashes2: list[str],
    ) -> np.ndarray:
        """Compute Hamming distances between two lists of hex hash strings."""

        def hex_to_binary(hex_str: str) -> np.ndarray:
            return np.array(
                [
                    int(b)
                    for b in bin(int(hex_str, 16))[2:].zfill(
                        len(hex_str) * 4,
                    )
                ],
            )

        arr1 = np.vstack(
            [hex_to_binary(h) for h in hashes1],
        ).astype(np.float32)
        arr2 = np.vstack(
            [hex_to_binary(h) for h in hashes2],
        ).astype(np.float32)

        if (
            self.backend == AcceleratorType.CUDA and self._torch is not None
        ):  # pragma: no cover
            return self._batch_hamming_torch(arr1, arr2)  # pragma: no cover
        if (
            self.backend == AcceleratorType.CUDA and self._cp is not None
        ):  # pragma: no cover
            return self._batch_hamming_cupy(arr1, arr2)  # pragma: no cover
        return self._batch_hamming_cpu(arr1, arr2)

    def _batch_hamming_torch(  # pragma: no cover
        self,
        arr1: np.ndarray,
        arr2: np.ndarray,
    ) -> np.ndarray:
        gpu1 = self._torch.from_numpy(arr1).to(self.torch_device)
        gpu2 = self._torch.from_numpy(arr2).to(self.torch_device)
        distances = (gpu1.unsqueeze(1) != gpu2.unsqueeze(0)).float().sum(dim=2)
        return distances.cpu().numpy()

    def _batch_hamming_cupy(  # pragma: no cover
        self,
        arr1: np.ndarray,
        arr2: np.ndarray,
    ) -> np.ndarray:
        gpu1 = self._cp.asarray(arr1)
        gpu2 = self._cp.asarray(arr2)
        distances = self._cp.sum(
            gpu1[:, self._cp.newaxis, :] != gpu2[self._cp.newaxis, :, :],
            axis=2,
        )
        return self._cp.asnumpy(distances)

    def _batch_hamming_cpu(
        self,
        arr1: np.ndarray,
        arr2: np.ndarray,
    ) -> np.ndarray:
        from scipy.spatial.distance import cdist

        distances = cdist(arr1, arr2, metric="hamming") * arr1.shape[1]
        return distances.astype(np.float32)


# ── Module-level convenience functions ─────────────────────────────────

_accelerator: GPUAccelerator | None = None


def get_accelerator() -> GPUAccelerator:
    """Get the global GPU accelerator instance."""
    global _accelerator
    if _accelerator is None:
        _accelerator = GPUAccelerator()
    return _accelerator


def compute_phash_gpu(
    images: list[np.ndarray],
    hash_size: int = 8,
) -> list[np.ndarray]:
    """Compute perceptual hashes for images using GPU acceleration."""
    acc = get_accelerator()
    if not images:
        return []

    dct_size = hash_size * 4

    gray_images = []
    for img in images:
        if len(img.shape) == 3:
            gray = np.dot(img[..., :3], [0.299, 0.587, 0.114])
        else:
            gray = img
        gray_images.append(gray.astype(np.float32))

    resized = acc.resize_image_batch(
        [img.astype(np.uint8) for img in gray_images],
        (dct_size, dct_size),
    )

    dct_results = acc.compute_dct_batch(
        [r.astype(np.float32) for r in resized],
    )

    hashes = []
    for dct in dct_results:
        low_freq = dct[:hash_size, :hash_size]
        median = np.median(low_freq)
        hash_bits = (low_freq > median).astype(np.uint8)
        hashes.append(hash_bits.flatten())

    return hashes


def compute_similarity_matrix_gpu(
    hashes: Sequence[str | np.ndarray],
    hash_size: int = 16,
) -> np.ndarray:
    """Compute pairwise similarity matrix for hashes using GPU."""
    acc = get_accelerator()
    if not hashes:
        return np.array([])

    if isinstance(hashes[0], str):

        def hex_to_binary(hex_str: str) -> np.ndarray:
            try:
                bits = bin(int(hex_str, 16))[2:].zfill(
                    hash_size * hash_size,
                )
                return np.array(
                    [int(b) for b in bits],
                    dtype=np.uint8,
                )
            except ValueError:
                return np.zeros(hash_size * hash_size, dtype=np.uint8)

        hash_arrays = [hex_to_binary(h) for h in hashes if isinstance(h, str)]
    else:
        hash_arrays = [
            h.flatten() if isinstance(h, np.ndarray) else np.array(h)
            for h in hashes
        ]

    return acc.compute_similarity_matrix(hash_arrays)

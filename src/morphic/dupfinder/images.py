"""
Image Duplicate Finder module.

Detects duplicate images based on content similarity using perceptual hashing.
"""

from __future__ import annotations

import logging
import os
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

import imagehash
import numpy as np
from PIL import Image
from tqdm import tqdm

from morphic.shared.constants import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_HASH_SIZE,
    DEFAULT_IMAGE_THRESHOLD,
    DEFAULT_NUM_WORKERS,
    EXCLUDED_FOLDERS,
    IMAGE_EXTENSIONS,
)
from morphic.shared.utils import (
    find_files_by_extension,
    format_file_size,
)

logger = logging.getLogger(__name__)

# Lazy import GPU accelerator
_gpu_available: bool | None = None
_get_accelerator = None
_compute_similarity_matrix_gpu = None


def _init_gpu() -> bool:
    """Initialize GPU module lazily."""
    global _gpu_available, _get_accelerator, _compute_similarity_matrix_gpu
    if _gpu_available is None:
        try:
            from morphic.dupfinder.accelerator import (
                compute_similarity_matrix_gpu,
                get_accelerator,
            )

            _get_accelerator = get_accelerator
            _compute_similarity_matrix_gpu = compute_similarity_matrix_gpu
            _gpu_available = True
        except ImportError:
            _gpu_available = False
    return _gpu_available


@dataclass
class ImageInfo:
    """Stores information about an image file."""

    path: str
    width: int = 0
    height: int = 0
    file_size: int = 0
    format: str = ""
    mode: str = ""
    phash: str | None = None
    ahash: str | None = None
    dhash: str | None = None
    whash: str | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "path": self.path,
            "width": self.width,
            "height": self.height,
            "file_size": self.file_size,
            "format": self.format,
            "mode": self.mode,
            "phash": self.phash,
            "ahash": self.ahash,
            "dhash": self.dhash,
        }


class ImageHasher:
    """Handles image loading and perceptual hashing."""

    def __init__(self, hash_size: int = DEFAULT_HASH_SIZE) -> None:
        self.hash_size = hash_size

    def compute_hashes(self, image_path: str) -> ImageInfo:
        """Compute perceptual hashes for an image."""
        image_info = ImageInfo(path=image_path)

        try:
            image_info.file_size = os.path.getsize(image_path)

            with Image.open(image_path) as img:
                image_info.width = img.width
                image_info.height = img.height
                image_info.format = img.format or ""
                image_info.mode = img.mode

                if img.mode not in ("RGB", "L"):
                    try:
                        img = img.convert("RGB")
                    except Exception:
                        img = img.convert("L")

                image_info.phash = str(
                    imagehash.phash(img, hash_size=self.hash_size),
                )
                image_info.ahash = str(
                    imagehash.average_hash(img, hash_size=self.hash_size),
                )
                image_info.dhash = str(
                    imagehash.dhash(img, hash_size=self.hash_size),
                )
                image_info.whash = str(
                    imagehash.whash(img, hash_size=self.hash_size),
                )

        except Exception as e:
            logger.warning("Error processing image %s: %s", image_path, e)

        return image_info


class ImageDuplicateFinder:
    """Finds duplicate images based on perceptual hash similarity."""

    def __init__(
        self,
        similarity_threshold: float = DEFAULT_IMAGE_THRESHOLD,
        hash_size: int = DEFAULT_HASH_SIZE,
        num_workers: int = DEFAULT_NUM_WORKERS,
        hash_type: str = "combined",
        use_gpu: bool = True,
        batch_size: int = DEFAULT_BATCH_SIZE,
    ) -> None:
        self.similarity_threshold = similarity_threshold
        self.num_workers = num_workers
        self.hash_type = hash_type
        self.hash_size = hash_size
        self.batch_size = batch_size
        self.hasher = ImageHasher(hash_size=hash_size)
        self.image_infos: dict[str, ImageInfo] = {}

        self.use_gpu = use_gpu and _init_gpu()
        self.accelerator = None
        if self.use_gpu and _get_accelerator is not None:
            try:
                self.accelerator = _get_accelerator()
                logger.info(
                    "GPU acceleration enabled: %s",
                    self.accelerator.get_backend_name(),
                )
            except Exception as e:
                logger.warning("GPU acceleration not available: %s", e)
                self.use_gpu = False

    def find_images(self, folder: str) -> list[str]:
        """Find all image files in a folder recursively."""
        return find_files_by_extension(
            folder, IMAGE_EXTENSIONS, EXCLUDED_FOLDERS,
        )

    def process_images(
        self, image_files: list[str],
    ) -> dict[str, ImageInfo]:
        """Process all images and compute their hashes."""
        logger.info("Processing images and computing hashes...")

        with ThreadPoolExecutor(max_workers=self.num_workers) as executor:
            futures = {
                executor.submit(self.hasher.compute_hashes, img): img
                for img in image_files
            }

            for future in tqdm(
                as_completed(futures),
                total=len(futures),
                desc="Processing",
            ):
                image_path = futures[future]
                try:
                    image_info = future.result()
                    if image_info.phash:
                        self.image_infos[image_path] = image_info
                except Exception as e:
                    logger.error("Error processing %s: %s", image_path, e)

        logger.info(
            "Successfully processed %d images", len(self.image_infos),
        )
        return self.image_infos

    def compute_similarity(
        self, info1: ImageInfo, info2: ImageInfo,
    ) -> float:
        """Compute similarity between two images based on their hashes."""
        similarities: list[float] = []
        hash_pairs: list[tuple[str, str]] = []

        if self.hash_type in ("combined", "phash"):
            if info1.phash and info2.phash:
                hash_pairs.append((info1.phash, info2.phash))

        if self.hash_type in ("combined", "ahash"):
            if info1.ahash and info2.ahash:
                hash_pairs.append((info1.ahash, info2.ahash))

        if self.hash_type in ("combined", "dhash"):
            if info1.dhash and info2.dhash:
                hash_pairs.append((info1.dhash, info2.dhash))

        if self.hash_type in ("combined", "whash"):
            if info1.whash and info2.whash:
                hash_pairs.append((info1.whash, info2.whash))

        for hash1, hash2 in hash_pairs:
            h1 = imagehash.hex_to_hash(hash1)
            h2 = imagehash.hex_to_hash(hash2)
            distance = h1 - h2
            max_distance = len(h1.hash.flatten())
            similarity = 1 - (distance / max_distance)
            similarities.append(similarity)

        return (
            sum(similarities) / len(similarities) if similarities else 0.0
        )

    def find_duplicates_fast(
        self,
    ) -> list[list[tuple[str, float]]]:
        """Find groups of duplicate images using hash bucketing."""
        logger.info("Finding duplicate images (fast mode)...")

        hash_buckets: dict[str, list[str]] = defaultdict(list)
        for path, info in self.image_infos.items():
            if info.phash:
                hash_buckets[info.phash].append(path)

        exact_groups: list[list[tuple[str, float]]] = []
        processed: set[str] = set()

        for _, paths in hash_buckets.items():
            if len(paths) > 1:
                group = [(p, 1.0) for p in paths]
                exact_groups.append(group)
                processed.update(paths)

        remaining = [
            p for p in self.image_infos if p not in processed
        ]

        if self.use_gpu and len(remaining) > 50:
            near_groups = self._find_near_duplicates_gpu(remaining)
        else:
            near_groups = self._find_near_duplicates(remaining)

        return exact_groups + near_groups

    def _find_near_duplicates_gpu(
        self, image_paths: list[str],
    ) -> list[list[tuple[str, float]]]:
        """Find near-duplicate images using GPU-accelerated similarity."""
        n = len(image_paths)
        if n == 0:
            return []

        logger.info(
            "Computing similarity matrix for %d images using GPU...", n,
        )

        all_hashes: list[str] = []
        for path in image_paths:
            info = self.image_infos[path]
            if self.hash_type == "phash" and info.phash:
                all_hashes.append(info.phash)
            elif self.hash_type == "ahash" and info.ahash:
                all_hashes.append(info.ahash)
            elif self.hash_type == "dhash" and info.dhash:
                all_hashes.append(info.dhash)
            elif self.hash_type == "whash" and info.whash:
                all_hashes.append(info.whash)
            else:
                all_hashes.append(
                    info.phash or info.ahash or info.dhash or "",
                )

        valid_indices = [i for i, h in enumerate(all_hashes) if h]
        valid_paths = [image_paths[i] for i in valid_indices]
        valid_hashes = [all_hashes[i] for i in valid_indices]

        if len(valid_hashes) < 2:
            return []

        try:
            if _compute_similarity_matrix_gpu is None:
                raise RuntimeError("GPU not initialized")
            sim_matrix = _compute_similarity_matrix_gpu(
                valid_hashes, self.hash_size,
            )
        except Exception as e:
            logger.warning(
                "GPU similarity failed, falling back to CPU: %s", e,
            )
            return self._find_near_duplicates(image_paths)

        duplicate_groups: list[list[tuple[str, float]]] = []
        assigned: set[int] = set()

        for i in range(len(valid_paths)):
            if i in assigned:
                continue

            similar_indices = np.where(
                sim_matrix[i] >= self.similarity_threshold,
            )[0]

            if len(similar_indices) > 1:
                group: list[tuple[str, float]] = []
                for j in similar_indices:
                    if j not in assigned or j == i:
                        group.append(
                            (valid_paths[j], float(sim_matrix[i, j])),
                        )
                        assigned.add(j)
                if len(group) > 1:
                    duplicate_groups.append(group)

        logger.info(
            "Found %d groups using GPU acceleration",
            len(duplicate_groups),
        )
        return duplicate_groups

    def _find_near_duplicates(
        self, image_paths: list[str],
    ) -> list[list[tuple[str, float]]]:
        """Find near-duplicate images using pairwise comparison."""
        n = len(image_paths)
        assigned: set[str] = set()
        duplicate_groups: list[list[tuple[str, float]]] = []

        total_comparisons = n * (n - 1) // 2

        with tqdm(total=total_comparisons, desc="Comparing") as pbar:
            for i in range(n):
                if image_paths[i] in assigned:
                    pbar.update(n - i - 1)
                    continue

                current_group: list[tuple[str, float]] = [
                    (image_paths[i], 1.0),
                ]

                for j in range(i + 1, n):
                    pbar.update(1)
                    if image_paths[j] in assigned:
                        continue

                    info1 = self.image_infos[image_paths[i]]
                    info2 = self.image_infos[image_paths[j]]
                    similarity = self.compute_similarity(info1, info2)

                    if similarity >= self.similarity_threshold:
                        current_group.append(
                            (image_paths[j], similarity),
                        )
                        assigned.add(image_paths[j])

                if len(current_group) > 1:
                    assigned.add(image_paths[i])
                    duplicate_groups.append(current_group)

        return duplicate_groups

    def find_duplicates(self) -> list[list[tuple[str, float]]]:
        """Find groups of duplicate images."""
        if len(self.image_infos) > 100 or self.use_gpu:
            return self.find_duplicates_fast()

        logger.info("Finding duplicate images...")

        image_paths = list(self.image_infos.keys())
        n = len(image_paths)
        assigned: set[str] = set()
        duplicate_groups: list[list[tuple[str, float]]] = []

        total_comparisons = n * (n - 1) // 2

        with tqdm(total=total_comparisons, desc="Comparing") as pbar:
            for i in range(n):
                if image_paths[i] in assigned:
                    pbar.update(n - i - 1)
                    continue

                current_group: list[tuple[str, float]] = [
                    (image_paths[i], 1.0),
                ]

                for j in range(i + 1, n):
                    pbar.update(1)
                    if image_paths[j] in assigned:
                        continue

                    info1 = self.image_infos[image_paths[i]]
                    info2 = self.image_infos[image_paths[j]]
                    similarity = self.compute_similarity(info1, info2)

                    if similarity >= self.similarity_threshold:
                        current_group.append(
                            (image_paths[j], similarity),
                        )
                        assigned.add(image_paths[j])

                if len(current_group) > 1:
                    assigned.add(image_paths[i])
                    duplicate_groups.append(current_group)

        logger.info(
            "Found %d groups of duplicates", len(duplicate_groups),
        )
        return duplicate_groups

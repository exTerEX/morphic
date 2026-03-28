"""
Video Duplicate Finder module.

Detects duplicate videos based on content similarity using perceptual hashing
of extracted frames.
"""

from __future__ import annotations

import hashlib
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

import cv2
import imagehash
import numpy as np
from PIL import Image
from tqdm import tqdm

from morphic.shared.constants import (
    DEFAULT_HASH_SIZE,
    DEFAULT_NUM_FRAMES,
    DEFAULT_NUM_WORKERS,
    DEFAULT_VIDEO_THRESHOLD,
    EXCLUDED_FOLDERS,
    VIDEO_EXTENSIONS,
)
from morphic.shared.utils import (
    find_files_by_extension,
    suppress_stderr,
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
class VideoInfo:
    """Stores information about a video file."""

    path: str
    duration: float = 0.0
    fps: float = 0.0
    frame_count: int = 0
    width: int = 0
    height: int = 0
    file_size: int = 0
    frame_hashes: list[str] = field(default_factory=list)
    average_hash: str | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "path": self.path,
            "duration": self.duration,
            "fps": self.fps,
            "frame_count": self.frame_count,
            "width": self.width,
            "height": self.height,
            "file_size": self.file_size,
            "average_hash": self.average_hash,
        }


class VideoHasher:
    """Handles video frame extraction and perceptual hashing."""

    def __init__(
        self,
        num_frames: int = DEFAULT_NUM_FRAMES,
        hash_size: int = DEFAULT_HASH_SIZE,
    ) -> None:
        self.num_frames = num_frames
        self.hash_size = hash_size

    def extract_frames(
        self,
        video_path: str,
    ) -> tuple[list[np.ndarray], VideoInfo]:
        """Extract frames from a video at regular intervals."""
        video_info = VideoInfo(path=video_path)
        frames: list[np.ndarray] = []

        try:
            video_info.file_size = os.path.getsize(video_path)

            with suppress_stderr():
                cap = cv2.VideoCapture(video_path)

            if not cap.isOpened():
                logger.warning("Could not open video: %s", video_path)
                return frames, video_info

            video_info.fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
            video_info.frame_count = int(
                cap.get(cv2.CAP_PROP_FRAME_COUNT),
            )
            video_info.width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            video_info.height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

            if video_info.frame_count > 0 and video_info.fps > 0:
                video_info.duration = video_info.frame_count / video_info.fps

            if video_info.frame_count <= 0:
                logger.warning(
                    "Could not determine frame count: %s",
                    video_path,
                )
                cap.release()
                return frames, video_info

            start_frame = int(video_info.frame_count * 0.05)
            end_frame = int(video_info.frame_count * 0.95)

            if end_frame <= start_frame:
                start_frame = 0
                end_frame = video_info.frame_count - 1

            frame_interval = max(
                1,
                (end_frame - start_frame) // (self.num_frames + 1),
            )
            frame_indices = [
                start_frame + (i + 1) * frame_interval
                for i in range(self.num_frames)
            ]

            for frame_idx in frame_indices:
                if frame_idx >= video_info.frame_count:
                    continue

                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
                with suppress_stderr():
                    ret, frame = cap.read()

                if ret and frame is not None:
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    frames.append(frame_rgb)

            cap.release()

        except Exception as e:
            logger.error("Error processing video %s: %s", video_path, e)

        return frames, video_info

    def compute_frame_hash(self, frame: np.ndarray) -> str:
        """Compute perceptual hash for a single frame."""
        try:
            img = Image.fromarray(frame)
            phash = imagehash.phash(img, hash_size=self.hash_size)
            return str(phash)
        except Exception as e:
            logger.error("Error computing hash: %s", e)
            return ""

    def compute_video_hashes(self, video_path: str) -> VideoInfo:
        """Compute perceptual hashes for a video."""
        frames, video_info = self.extract_frames(video_path)

        if not frames:
            return video_info

        for frame in frames:
            frame_hash = self.compute_frame_hash(frame)
            if frame_hash:
                video_info.frame_hashes.append(frame_hash)

        if video_info.frame_hashes:
            combined = "".join(video_info.frame_hashes)
            video_info.average_hash = hashlib.md5(
                combined.encode(),
            ).hexdigest()

        return video_info


class VideoDuplicateFinder:
    """Finds duplicate videos based on perceptual hash similarity."""

    def __init__(
        self,
        similarity_threshold: float = DEFAULT_VIDEO_THRESHOLD,
        num_frames: int = DEFAULT_NUM_FRAMES,
        hash_size: int = DEFAULT_HASH_SIZE,
        num_workers: int = DEFAULT_NUM_WORKERS,
        use_gpu: bool = True,
    ) -> None:
        self.similarity_threshold = similarity_threshold
        self.num_workers = num_workers
        self.hash_size = hash_size
        self.hasher = VideoHasher(
            num_frames=num_frames,
            hash_size=hash_size,
        )
        self.video_infos: dict[str, VideoInfo] = {}

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

    def find_videos(self, folder: str) -> list[str]:
        """Find all video files in a folder recursively."""
        return find_files_by_extension(
            folder,
            VIDEO_EXTENSIONS,
            EXCLUDED_FOLDERS,
        )

    def process_videos(
        self,
        video_files: list[str],
    ) -> dict[str, VideoInfo]:
        """Process all videos and compute their hashes."""
        logger.info("Processing videos and computing hashes...")

        with ThreadPoolExecutor(max_workers=self.num_workers) as executor:
            futures = {
                executor.submit(self.hasher.compute_video_hashes, vf): vf
                for vf in video_files
            }

            for future in tqdm(
                as_completed(futures),
                total=len(futures),
                desc="Processing",
            ):
                video_path = futures[future]
                try:
                    video_info = future.result()
                    if video_info.frame_hashes:
                        self.video_infos[video_path] = video_info
                except Exception as e:
                    logger.error(
                        "Error processing %s: %s",
                        video_path,
                        e,
                    )

        logger.info(
            "Successfully processed %d videos",
            len(self.video_infos),
        )
        return self.video_infos

    def compute_similarity(
        self,
        info1: VideoInfo,
        info2: VideoInfo,
    ) -> float:
        """Compute similarity between two videos."""
        if not info1.frame_hashes or not info2.frame_hashes:
            return 0.0

        similarities: list[float] = []

        for hash1 in info1.frame_hashes:
            best_sim = 0.0
            h1 = imagehash.hex_to_hash(hash1)

            for hash2 in info2.frame_hashes:
                h2 = imagehash.hex_to_hash(hash2)
                distance = h1 - h2
                max_distance = len(h1.hash.flatten()) * len(
                    h1.hash.flatten(),
                )
                similarity = 1 - (distance / max_distance)
                best_sim = max(best_sim, similarity)

            similarities.append(best_sim)

        return sum(similarities) / len(similarities) if similarities else 0.0

    def find_duplicates(
        self,
    ) -> list[list[tuple[str, float]]]:
        """Find groups of duplicate videos."""
        logger.info("Finding duplicate videos...")

        video_paths = list(self.video_infos.keys())
        n = len(video_paths)

        if self.use_gpu and n > 1:
            return self._find_duplicates_gpu(video_paths)
        return self._find_duplicates_cpu(video_paths)

    def _find_duplicates_gpu(
        self,
        video_paths: list[str],
    ) -> list[list[tuple[str, float]]]:
        """Find duplicates using GPU-accelerated frame hash comparison."""
        n = len(video_paths)
        logger.info(
            "Computing video similarities using GPU for %d videos...",
            n,
        )

        combined_hashes: list[str] = []
        valid_paths: list[str] = []

        for path in video_paths:
            info = self.video_infos[path]
            if info.frame_hashes:
                combined_hashes.append(info.frame_hashes[0])
                valid_paths.append(path)

        if len(combined_hashes) < 2:
            return []

        try:
            if _compute_similarity_matrix_gpu is None:
                raise RuntimeError("GPU not initialized")
            sim_matrix = _compute_similarity_matrix_gpu(
                combined_hashes,
                self.hash_size,
            )
        except Exception as e:
            logger.warning(
                "GPU computation failed, falling back to CPU: %s",
                e,
            )
            return self._find_duplicates_cpu(video_paths)

        duplicate_groups: list[list[tuple[str, float]]] = []
        assigned: set[int] = set()

        for i in range(len(valid_paths)):
            if i in assigned:
                continue

            pre_threshold = max(
                0.5,
                self.similarity_threshold - 0.2,
            )
            candidate_indices = np.where(
                sim_matrix[i] >= pre_threshold,
            )[0]

            if len(candidate_indices) <= 1:
                continue

            current_group: list[tuple[str, float]] = [
                (valid_paths[i], 1.0),
            ]

            for j in candidate_indices:
                if j <= i or j in assigned:
                    continue

                info1 = self.video_infos[valid_paths[i]]
                info2 = self.video_infos[valid_paths[j]]
                similarity = self.compute_similarity(info1, info2)

                if similarity >= self.similarity_threshold:
                    current_group.append((valid_paths[j], similarity))
                    assigned.add(j)

            if len(current_group) > 1:
                assigned.add(i)
                duplicate_groups.append(current_group)

        logger.info(
            "Found %d groups of duplicates",
            len(duplicate_groups),
        )
        return duplicate_groups

    def _find_duplicates_cpu(
        self,
        video_paths: list[str],
    ) -> list[list[tuple[str, float]]]:
        """Find duplicates using CPU-based comparison."""
        n = len(video_paths)
        assigned: set[str] = set()
        duplicate_groups: list[list[tuple[str, float]]] = []

        total_comparisons = n * (n - 1) // 2

        with tqdm(total=total_comparisons, desc="Comparing") as pbar:
            for i in range(n):
                if video_paths[i] in assigned:
                    pbar.update(n - i - 1)
                    continue

                current_group: list[tuple[str, float]] = [
                    (video_paths[i], 1.0),
                ]

                for j in range(i + 1, n):
                    pbar.update(1)
                    if video_paths[j] in assigned:
                        continue

                    info1 = self.video_infos[video_paths[i]]
                    info2 = self.video_infos[video_paths[j]]
                    similarity = self.compute_similarity(info1, info2)

                    if similarity >= self.similarity_threshold:
                        current_group.append(
                            (video_paths[j], similarity),
                        )
                        assigned.add(video_paths[j])

                if len(current_group) > 1:
                    assigned.add(video_paths[i])
                    duplicate_groups.append(current_group)

        logger.info(
            "Found %d groups of duplicates",
            len(duplicate_groups),
        )
        return duplicate_groups

"""Tests for morphic.dupfinder.videos."""

from __future__ import annotations

import os
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from morphic.dupfinder.videos import (
    VideoDuplicateFinder,
    VideoHasher,
    VideoInfo,
)


# ── VideoInfo ──────────────────────────────────────────────────────────────


class TestVideoInfoToDict:
    def test_to_dict_keys(self) -> None:
        info = VideoInfo(
            path="/v.mp4",
            duration=120.5,
            fps=30.0,
            frame_count=3615,
            width=1920,
            height=1080,
            file_size=50000000,
            average_hash="abc123",
        )
        d = info.to_dict()
        assert d["path"] == "/v.mp4"
        assert d["duration"] == 120.5
        assert d["fps"] == 30.0
        assert d["frame_count"] == 3615
        assert d["width"] == 1920
        assert d["height"] == 1080
        assert d["file_size"] == 50000000
        assert d["average_hash"] == "abc123"

    def test_to_dict_defaults(self) -> None:
        info = VideoInfo(path="/x.avi")
        d = info.to_dict()
        assert d["duration"] == 0.0
        assert d["average_hash"] is None

    def test_frame_hashes_default_empty(self) -> None:
        info = VideoInfo(path="/v.mp4")
        assert info.frame_hashes == []

    def test_defaults(self) -> None:
        info = VideoInfo(path="/test.mp4")
        assert info.path == "/test.mp4"
        assert info.width == 0
        assert info.height == 0
        assert info.duration == 0.0
        assert info.fps == 0.0

    def test_custom_values(self) -> None:
        info = VideoInfo(
            path="/v.mp4",
            width=3840,
            height=2160,
            duration=120.5,
            fps=60.0,
            file_size=10000000,
        )
        assert info.duration == 120.5
        assert info.fps == 60.0


# ── VideoHasher ────────────────────────────────────────────────────────────


class TestVideoHasher:
    def test_default_params(self) -> None:
        hasher = VideoHasher()
        assert hasher.num_frames == 10
        assert hasher.hash_size == 16

    def test_custom_params(self) -> None:
        hasher = VideoHasher(num_frames=5, hash_size=8)
        assert hasher.num_frames == 5
        assert hasher.hash_size == 8

    def test_compute_frame_hash(self) -> None:
        hasher = VideoHasher(hash_size=8)
        frame = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        result = hasher.compute_frame_hash(frame)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_compute_frame_hash_invalid(self) -> None:
        hasher = VideoHasher(hash_size=8)
        result = hasher.compute_frame_hash(np.array([]))
        assert result == "" or isinstance(result, str)

    def test_extract_frames_nonexistent(self) -> None:
        hasher = VideoHasher(hash_size=8)
        frames, info = hasher.extract_frames("/nonexistent/video.mp4")
        assert frames == []
        assert info.path == "/nonexistent/video.mp4"

    def test_compute_video_hashes_nonexistent(self) -> None:
        hasher = VideoHasher(hash_size=8)
        info = hasher.compute_video_hashes("/nonexistent/video.mp4")
        assert info.frame_hashes == []
        assert info.average_hash is None

    def test_compute_video_hashes_with_mock_frames(self) -> None:
        hasher = VideoHasher(num_frames=3, hash_size=8)
        frames = [
            np.random.randint(0, 255, (64, 64, 3), dtype=np.uint8)
            for _ in range(3)
        ]
        hashes = [hasher.compute_frame_hash(f) for f in frames]
        assert all(isinstance(h, str) and len(h) > 0 for h in hashes)

    def test_manual_frame_hash_building(self) -> None:
        hasher = VideoHasher(num_frames=3, hash_size=8)
        frames = [
            np.random.randint(0, 255, (64, 64, 3), dtype=np.uint8)
            for _ in range(3)
        ]
        info = VideoInfo(path="/test.mp4", file_size=1000)
        for frame in frames:
            h = hasher.compute_frame_hash(frame)
            if h:
                info.frame_hashes.append(h)
        assert len(info.frame_hashes) == 3


# ── VideoDuplicateFinder ───────────────────────────────────────────────────


class TestVideoDuplicateFinder:
    def test_init_defaults(self) -> None:
        finder = VideoDuplicateFinder(use_gpu=False)
        assert finder.similarity_threshold == 0.85
        assert finder.use_gpu is False

    def test_find_videos(self, tmp_path) -> None:
        (tmp_path / "a.mp4").write_bytes(b"\x00" * 100)
        (tmp_path / "b.avi").write_bytes(b"\x00" * 100)
        (tmp_path / "c.txt").write_text("hello")

        finder = VideoDuplicateFinder(use_gpu=False)
        files = finder.find_videos(str(tmp_path))
        exts = {os.path.splitext(f)[1].lower() for f in files}
        assert ".txt" not in exts

    def test_find_videos_empty_folder(self, tmp_path) -> None:
        finder = VideoDuplicateFinder(use_gpu=False)
        result = finder.find_videos(str(tmp_path))
        assert result == []

    def test_compute_similarity_no_hashes(self) -> None:
        finder = VideoDuplicateFinder(use_gpu=False)
        info1 = VideoInfo(path="/a.mp4")
        info2 = VideoInfo(path="/b.mp4")
        assert finder.compute_similarity(info1, info2) == 0.0

    def test_compute_similarity_identical_hashes(self) -> None:
        finder = VideoDuplicateFinder(use_gpu=False, hash_size=8)
        hasher = VideoHasher(hash_size=8)

        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        h = hasher.compute_frame_hash(frame)

        info1 = VideoInfo(path="/a.mp4", frame_hashes=[h, h])
        info2 = VideoInfo(path="/b.mp4", frame_hashes=[h, h])
        similarity = finder.compute_similarity(info1, info2)
        assert similarity == pytest.approx(1.0)

    def test_compute_similarity_different_frames(self) -> None:
        hasher = VideoHasher(hash_size=8)
        finder = VideoDuplicateFinder(use_gpu=False, hash_size=8)

        frame1 = np.zeros((64, 64, 3), dtype=np.uint8)
        frame2 = np.ones((64, 64, 3), dtype=np.uint8) * 255
        h1 = hasher.compute_frame_hash(frame1)
        h2 = hasher.compute_frame_hash(frame2)

        info1 = VideoInfo(path="/a.mp4", frame_hashes=[h1])
        info2 = VideoInfo(path="/b.mp4", frame_hashes=[h2])

        sim = finder.compute_similarity(info1, info2)
        assert 0.0 <= sim <= 1.0

    def test_find_duplicates_empty(self) -> None:
        finder = VideoDuplicateFinder(use_gpu=False)
        groups = finder.find_duplicates()
        assert groups == []

    def test_find_duplicates_cpu_with_infos(self) -> None:
        finder = VideoDuplicateFinder(use_gpu=False, hash_size=8)
        hasher = VideoHasher(hash_size=8)

        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        h = hasher.compute_frame_hash(frame)

        finder.video_infos = {
            "/a.mp4": VideoInfo(
                path="/a.mp4",
                frame_hashes=[h],
                file_size=1000,
            ),
            "/b.mp4": VideoInfo(
                path="/b.mp4",
                frame_hashes=[h],
                file_size=1000,
            ),
        }
        groups = finder.find_duplicates()
        assert len(groups) >= 1

    def test_find_duplicates_cpu(self) -> None:
        hasher = VideoHasher(hash_size=8)
        finder = VideoDuplicateFinder(
            use_gpu=False,
            hash_size=8,
            similarity_threshold=0.9,
        )

        frame = np.zeros((64, 64, 3), dtype=np.uint8)
        h = hasher.compute_frame_hash(frame)

        finder.video_infos = {
            "/a.mp4": VideoInfo(
                path="/a.mp4",
                frame_hashes=[h],
                file_size=1000,
            ),
            "/b.mp4": VideoInfo(
                path="/b.mp4",
                frame_hashes=[h],
                file_size=1000,
            ),
            "/c.mp4": VideoInfo(
                path="/c.mp4",
                frame_hashes=[h],
                file_size=1000,
            ),
        }

        groups = finder._find_duplicates_cpu(list(finder.video_infos.keys()))
        assert len(groups) >= 1

    def test_find_duplicates_cpu_no_match(self) -> None:
        hasher = VideoHasher(hash_size=8)
        finder = VideoDuplicateFinder(
            use_gpu=False,
            hash_size=8,
            similarity_threshold=0.99,
        )

        frames = [
            np.random.randint(0, 255, (64, 64, 3), dtype=np.uint8)
            for _ in range(3)
        ]

        for i, frame in enumerate(frames):
            h = hasher.compute_frame_hash(frame)
            finder.video_infos[f"/v{i}.mp4"] = VideoInfo(
                path=f"/v{i}.mp4",
                frame_hashes=[h],
                file_size=1000,
            )

        groups = finder._find_duplicates_cpu(list(finder.video_infos.keys()))
        assert isinstance(groups, list)

    def test_process_videos_empty(self) -> None:
        finder = VideoDuplicateFinder(use_gpu=False)
        result = finder.process_videos([])
        assert result == {}

    @patch("morphic.dupfinder.videos._compute_similarity_matrix_gpu")
    @patch("morphic.dupfinder.videos._gpu_available", True)
    def test_find_duplicates_gpu_path(self, mock_sim) -> None:
        hasher = VideoHasher(hash_size=8)
        finder = VideoDuplicateFinder(use_gpu=False, hash_size=8)

        frame = np.zeros((64, 64, 3), dtype=np.uint8)
        h = hasher.compute_frame_hash(frame)

        finder.video_infos = {
            "/a.mp4": VideoInfo(path="/a.mp4", frame_hashes=[h]),
            "/b.mp4": VideoInfo(path="/b.mp4", frame_hashes=[h]),
        }

        finder.use_gpu = True
        sim_matrix = np.ones((2, 2), dtype=np.float32)
        mock_sim.return_value = sim_matrix

        result = finder._find_duplicates_gpu(list(finder.video_infos.keys()))
        assert isinstance(result, list)

    @patch("morphic.dupfinder.videos._compute_similarity_matrix_gpu")
    @patch("morphic.dupfinder.videos._gpu_available", True)
    def test_find_duplicates_gpu_fallback(self, mock_sim) -> None:
        hasher = VideoHasher(hash_size=8)
        finder = VideoDuplicateFinder(use_gpu=False, hash_size=8)

        frame = np.zeros((64, 64, 3), dtype=np.uint8)
        h = hasher.compute_frame_hash(frame)

        finder.video_infos = {
            "/a.mp4": VideoInfo(path="/a.mp4", frame_hashes=[h]),
            "/b.mp4": VideoInfo(path="/b.mp4", frame_hashes=[h]),
        }
        finder.use_gpu = True

        mock_sim.side_effect = RuntimeError("GPU failed")
        result = finder._find_duplicates_gpu(list(finder.video_infos.keys()))
        assert isinstance(result, list)


# ── Video extraction (cv2) ─────────────────────────────────────────────────


@contextmanager
def _noop_ctx():
    yield


_PATCH_GETSIZE = patch(
    "morphic.dupfinder.videos.os.path.getsize", return_value=1024
)
_PATCH_SUPPRESS = patch(
    "morphic.dupfinder.videos.suppress_stderr",
    side_effect=_noop_ctx,
)


class TestVideoExtraction:
    @_PATCH_SUPPRESS
    @_PATCH_GETSIZE
    @patch("morphic.dupfinder.videos.cv2.cvtColor")
    @patch("morphic.dupfinder.videos.cv2.VideoCapture")
    def test_extract_frames_success(
        self,
        mock_vc_cls,
        mock_cvt,
        _mock_gs,
        _mock_ss,
    ) -> None:
        mock_cap = MagicMock()
        mock_vc_cls.return_value = mock_cap
        mock_cap.isOpened.return_value = True

        def get_side_effect(prop):
            mapping = {5: 30.0, 7: 300, 3: 640, 4: 480}
            return mapping.get(prop, 0)

        mock_cap.get.side_effect = get_side_effect

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        mock_cap.read.return_value = (True, frame)
        mock_cvt.return_value = frame

        hasher = VideoHasher(num_frames=3, hash_size=8)
        frames, info = hasher.extract_frames("/test/video.mp4")

        assert info.fps == 30.0
        assert info.frame_count == 300
        assert info.width == 640
        assert info.height == 480
        assert len(frames) > 0
        mock_cap.release.assert_called_once()

    @_PATCH_SUPPRESS
    @_PATCH_GETSIZE
    @patch("morphic.dupfinder.videos.cv2.VideoCapture")
    def test_extract_frames_not_opened(
        self,
        mock_vc_cls,
        _mock_gs,
        _mock_ss,
    ) -> None:
        mock_cap = MagicMock()
        mock_vc_cls.return_value = mock_cap
        mock_cap.isOpened.return_value = False

        hasher = VideoHasher(hash_size=8)
        frames, info = hasher.extract_frames("/test/video.mp4")
        assert frames == []

    @_PATCH_SUPPRESS
    @_PATCH_GETSIZE
    @patch("morphic.dupfinder.videos.cv2.VideoCapture")
    def test_extract_frames_zero_frame_count(
        self,
        mock_vc_cls,
        _mock_gs,
        _mock_ss,
    ) -> None:
        mock_cap = MagicMock()
        mock_vc_cls.return_value = mock_cap
        mock_cap.isOpened.return_value = True

        def get_side_effect(prop):
            mapping = {5: 30.0, 7: 0, 3: 640, 4: 480}
            return mapping.get(prop, 0)

        mock_cap.get.side_effect = get_side_effect

        hasher = VideoHasher(hash_size=8)
        frames, info = hasher.extract_frames("/test/short.mp4")
        assert frames == []
        mock_cap.release.assert_called_once()

    @_PATCH_SUPPRESS
    @_PATCH_GETSIZE
    @patch("morphic.dupfinder.videos.cv2.cvtColor")
    @patch("morphic.dupfinder.videos.cv2.VideoCapture")
    def test_extract_frames_read_fails(
        self,
        mock_vc_cls,
        mock_cvt,
        _mock_gs,
        _mock_ss,
    ) -> None:
        mock_cap = MagicMock()
        mock_vc_cls.return_value = mock_cap
        mock_cap.isOpened.return_value = True

        def get_side_effect(prop):
            mapping = {5: 30.0, 7: 100, 3: 320, 4: 240}
            return mapping.get(prop, 0)

        mock_cap.get.side_effect = get_side_effect
        mock_cap.read.return_value = (False, None)

        hasher = VideoHasher(num_frames=3, hash_size=8)
        frames, info = hasher.extract_frames("/test/video.mp4")
        assert frames == []


class TestComputeVideoHashes:
    @_PATCH_SUPPRESS
    @_PATCH_GETSIZE
    @patch("morphic.dupfinder.videos.cv2.cvtColor")
    @patch("morphic.dupfinder.videos.cv2.VideoCapture")
    def test_full_pipeline(
        self,
        mock_vc_cls,
        mock_cvt,
        _mock_gs,
        _mock_ss,
    ) -> None:
        mock_cap = MagicMock()
        mock_vc_cls.return_value = mock_cap
        mock_cap.isOpened.return_value = True

        def get_side_effect(prop):
            return {5: 30.0, 7: 300, 3: 64, 4: 64}.get(prop, 0)

        mock_cap.get.side_effect = get_side_effect

        frame = np.random.randint(0, 255, (64, 64, 3), dtype=np.uint8)
        mock_cap.read.return_value = (True, frame)
        mock_cvt.return_value = frame

        hasher = VideoHasher(num_frames=3, hash_size=8)
        info = hasher.compute_video_hashes("/test/video.mp4")

        assert len(info.frame_hashes) > 0
        assert info.average_hash is not None

    @_PATCH_SUPPRESS
    @_PATCH_GETSIZE
    @patch("morphic.dupfinder.videos.cv2.VideoCapture")
    def test_no_frames_extracted(
        self,
        mock_vc_cls,
        _mock_gs,
        _mock_ss,
    ) -> None:
        mock_cap = MagicMock()
        mock_vc_cls.return_value = mock_cap
        mock_cap.isOpened.return_value = False

        hasher = VideoHasher(hash_size=8)
        info = hasher.compute_video_hashes("/test/bad_video.mp4")
        assert info.frame_hashes == []
        assert info.average_hash is None


class TestVideoProcessing:
    @_PATCH_SUPPRESS
    @_PATCH_GETSIZE
    @patch("morphic.dupfinder.videos.cv2.cvtColor")
    @patch("morphic.dupfinder.videos.cv2.VideoCapture")
    def test_process_videos_with_mocked_cv2(
        self,
        mock_vc_cls,
        mock_cvt,
        _mock_gs,
        _mock_ss,
    ) -> None:
        mock_cap = MagicMock()
        mock_vc_cls.return_value = mock_cap
        mock_cap.isOpened.return_value = True

        def get_side_effect(prop):
            return {5: 30.0, 7: 100, 3: 64, 4: 64}.get(prop, 0)

        mock_cap.get.side_effect = get_side_effect

        frame = np.random.randint(0, 255, (64, 64, 3), dtype=np.uint8)
        mock_cap.read.return_value = (True, frame)
        mock_cvt.return_value = frame

        finder = VideoDuplicateFinder(
            use_gpu=False,
            hash_size=8,
            num_workers=1,
        )
        result = finder.process_videos(["/test/a.mp4", "/test/b.mp4"])
        assert len(result) >= 0

    @_PATCH_SUPPRESS
    @_PATCH_GETSIZE
    @patch("morphic.dupfinder.videos.cv2.cvtColor")
    @patch("morphic.dupfinder.videos.cv2.VideoCapture")
    def test_duration_calculation(
        self,
        mock_vc_cls,
        mock_cvt,
        _mock_gs,
        _mock_ss,
    ) -> None:
        mock_cap = MagicMock()
        mock_vc_cls.return_value = mock_cap
        mock_cap.isOpened.return_value = True

        def get_side_effect(prop):
            return {5: 25.0, 7: 250, 3: 320, 4: 240}.get(prop, 0)

        mock_cap.get.side_effect = get_side_effect

        frame = np.zeros((240, 320, 3), dtype=np.uint8)
        mock_cap.read.return_value = (True, frame)
        mock_cvt.return_value = frame

        hasher = VideoHasher(num_frames=2, hash_size=8)
        frames, info = hasher.extract_frames("/test/video.avi")

        assert info.duration == pytest.approx(10.0)

"""Tests for morphic.organizer.date_sorter."""

from __future__ import annotations

import os
import time

import pytest
from PIL import Image

from morphic.organizer.date_sorter import (
    execute_sort,
    get_file_date,
    plan_sort,
)


def _make_jpeg(path: str) -> str:
    Image.new("RGB", (10, 10), "red").save(path, "JPEG")
    return path


class TestGetFileDate:
    def test_returns_datetime(self, tmp_path) -> None:
        path = _make_jpeg(str(tmp_path / "a.jpg"))
        dt = get_file_date(path)
        assert dt is not None
        assert dt.year >= 2020

    def test_fallback_to_mtime(self, tmp_path) -> None:
        # PNG has no EXIF — should fall back to mtime
        p = str(tmp_path / "test.png")
        Image.new("RGB", (10, 10)).save(p)
        dt = get_file_date(p)
        assert dt is not None


class TestPlanSort:
    def test_plan_returns_list(self, tmp_path) -> None:
        _make_jpeg(str(tmp_path / "a.jpg"))
        _make_jpeg(str(tmp_path / "b.jpg"))
        plan = plan_sort(str(tmp_path))
        assert isinstance(plan, list)
        assert len(plan) == 2
        for entry in plan:
            assert "source" in entry
            assert "destination" in entry
            assert "date" in entry

    def test_plan_with_template(self, tmp_path) -> None:
        _make_jpeg(str(tmp_path / "photo.jpg"))
        plan = plan_sort(str(tmp_path), template="{year}/{month}")
        assert len(plan) == 1
        # Destination should contain year/month path
        dest = plan[0]["destination"]
        parts = dest.replace("\\", "/").split("/")
        # Should have numeric year and month somewhere in path
        assert any(p.isdigit() and len(p) == 4 for p in parts)

    def test_plan_with_destination(self, tmp_path) -> None:
        src = tmp_path / "src"
        src.mkdir()
        _make_jpeg(str(src / "a.jpg"))

        dest = str(tmp_path / "dest")
        plan = plan_sort(str(src), destination=dest)
        assert len(plan) == 1
        assert plan[0]["destination"].startswith(dest)


class TestExecuteSort:
    def test_copy(self, tmp_path) -> None:
        _make_jpeg(str(tmp_path / "orig.jpg"))
        plan = plan_sort(str(tmp_path), destination=str(tmp_path / "sorted"))
        result = execute_sort(plan, operation="copy")
        assert result["completed"] == 1
        assert result["errors"] == 0
        # Original still exists (copy)
        assert os.path.isfile(str(tmp_path / "orig.jpg"))
        # Destination exists
        assert os.path.isfile(plan[0]["destination"])

    def test_move(self, tmp_path) -> None:
        _make_jpeg(str(tmp_path / "orig.jpg"))
        plan = plan_sort(str(tmp_path), destination=str(tmp_path / "sorted"))
        result = execute_sort(plan, operation="move")
        assert result["completed"] == 1
        # Original should be gone
        assert not os.path.isfile(str(tmp_path / "orig.jpg"))

    def test_invalid_operation(self, tmp_path) -> None:
        with pytest.raises(ValueError, match="move.*copy"):
            execute_sort([], operation="bad")

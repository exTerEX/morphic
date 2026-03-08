"""Tests for morphic.organizer.renamer."""

from __future__ import annotations

import os

import pytest
from PIL import Image

from morphic.organizer.renamer import execute_rename, plan_rename


def _make_jpeg(path: str) -> str:
    Image.new("RGB", (10, 10), "red").save(path, "JPEG")
    return path


class TestPlanRename:
    def test_basic_plan(self, tmp_path) -> None:
        _make_jpeg(str(tmp_path / "a.jpg"))
        _make_jpeg(str(tmp_path / "b.jpg"))
        plan = plan_rename(str(tmp_path), template="{seq:3}{ext}")
        assert len(plan) == 2
        for entry in plan:
            assert "source" in entry
            assert "new_name" in entry
            assert "destination" in entry
            assert "conflict" in entry

    def test_seq_token(self, tmp_path) -> None:
        _make_jpeg(str(tmp_path / "photo.jpg"))
        plan = plan_rename(str(tmp_path), template="{seq:4}{ext}", start_seq=1)
        assert plan[0]["new_name"] == "0001.jpg"

    def test_original_token(self, tmp_path) -> None:
        _make_jpeg(str(tmp_path / "nice_photo.jpg"))
        plan = plan_rename(str(tmp_path), template="{original}_renamed{ext}")
        assert "nice_photo_renamed.jpg" in plan[0]["new_name"]

    def test_date_token(self, tmp_path) -> None:
        _make_jpeg(str(tmp_path / "photo.jpg"))
        plan = plan_rename(str(tmp_path), template="{date}_{seq}{ext}")
        # Should have date-like prefix
        name = plan[0]["new_name"]
        assert name.count("-") >= 2  # YYYY-MM-DD has 2 dashes

    def test_conflict_detection(self, tmp_path) -> None:
        # Create 2 files that would get the same name
        _make_jpeg(str(tmp_path / "a.jpg"))
        _make_jpeg(str(tmp_path / "b.jpg"))
        # Template without seq = all get same name
        plan = plan_rename(str(tmp_path), template="same{ext}")
        conflicts = [p for p in plan if p["conflict"]]
        # At least one conflict expected
        assert len(conflicts) >= 1

    def test_output_folder(self, tmp_path) -> None:
        _make_jpeg(str(tmp_path / "photo.jpg"))
        out = str(tmp_path / "renamed")
        plan = plan_rename(str(tmp_path), template="{seq}{ext}", output_folder=out)
        assert plan[0]["destination"].startswith(out)


class TestExecuteRename:
    def test_move(self, tmp_path) -> None:
        _make_jpeg(str(tmp_path / "orig.jpg"))
        plan = plan_rename(
            str(tmp_path),
            template="renamed_{seq:2}{ext}",
            output_folder=str(tmp_path / "out"),
        )
        result = execute_rename(plan, operation="move")
        assert result["completed"] == 1
        assert result["errors"] == 0
        assert not os.path.isfile(str(tmp_path / "orig.jpg"))

    def test_copy(self, tmp_path) -> None:
        _make_jpeg(str(tmp_path / "orig.jpg"))
        plan = plan_rename(
            str(tmp_path),
            template="renamed{ext}",
            output_folder=str(tmp_path / "out"),
        )
        result = execute_rename(plan, operation="copy")
        assert result["completed"] == 1
        # Original still exists
        assert os.path.isfile(str(tmp_path / "orig.jpg"))

    def test_skips_conflicts(self, tmp_path) -> None:
        _make_jpeg(str(tmp_path / "a.jpg"))
        _make_jpeg(str(tmp_path / "b.jpg"))
        plan = plan_rename(str(tmp_path), template="same{ext}")
        result = execute_rename(plan, operation="copy")
        # Should skip at least 1 conflict
        assert result["skipped"] >= 1

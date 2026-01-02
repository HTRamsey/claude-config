"""Tests for handlers/project_context.py"""
import tempfile
from pathlib import Path

import pytest


class TestProjectContext:
    """Tests for project context handler."""

    def test_detect_project_type_python(self):
        from hooks.handlers.project_context import detect_project_type
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "pyproject.toml").touch()
            result = detect_project_type(tmpdir)
            assert "Python" in result

    def test_detect_project_type_empty(self):
        from hooks.handlers.project_context import detect_project_type
        with tempfile.TemporaryDirectory() as tmpdir:
            result = detect_project_type(tmpdir)
            assert result == ""

    def test_get_todo_context_missing(self):
        from hooks.handlers.project_context import get_todo_context
        with tempfile.TemporaryDirectory() as tmpdir:
            result = get_todo_context(tmpdir)
            assert result == ""

    def test_get_todo_context_exists(self):
        from hooks.handlers.project_context import get_todo_context
        with tempfile.TemporaryDirectory() as tmpdir:
            todo = Path(tmpdir) / "TODO.md"
            todo.write_text("# Tasks\n- Task 1\n- Task 2\n")
            result = get_todo_context(tmpdir)
            assert "TODO.md" in result
            assert "Task 1" in result

    def test_get_codebase_map_empty(self):
        from hooks.handlers.project_context import get_codebase_map
        with tempfile.TemporaryDirectory() as tmpdir:
            result = get_codebase_map(tmpdir)
            assert result == ""

    def test_get_codebase_map_with_files(self):
        from hooks.handlers.project_context import get_codebase_map
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "src").mkdir()
            (Path(tmpdir) / "src" / "main.py").touch()
            result = get_codebase_map(tmpdir)
            assert "src/" in result
            assert "main.py" in result

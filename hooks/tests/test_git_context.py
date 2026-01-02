"""Tests for handlers/git_context.py"""
import tempfile

import pytest


class TestGitContext:
    """Tests for git context handler."""

    def test_run_cmd_success(self):
        from hooks.handlers.git_context import run_cmd
        result = run_cmd(["echo", "hello"])
        assert result == "hello"

    def test_run_cmd_failure(self):
        from hooks.handlers.git_context import run_cmd
        result = run_cmd(["false"])
        assert result == ""

    def test_run_cmd_timeout(self):
        from hooks.handlers.git_context import run_cmd
        result = run_cmd(["sleep", "10"], timeout=0.1)
        assert result == ""

    def test_is_git_repo_false(self):
        from hooks.handlers.git_context import is_git_repo
        with tempfile.TemporaryDirectory() as tmpdir:
            assert is_git_repo(tmpdir) is False

    def test_get_status_not_repo(self):
        from hooks.handlers.git_context import get_status
        with tempfile.TemporaryDirectory() as tmpdir:
            status = get_status(tmpdir)
            assert status["is_git_repo"] is False
            assert status["branch"] == ""

    def test_get_context_summary_not_repo(self):
        from hooks.handlers.git_context import get_context_summary
        with tempfile.TemporaryDirectory() as tmpdir:
            context = get_context_summary(tmpdir)
            assert context == []

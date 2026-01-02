"""Tests for handlers/session_persistence.py"""
import pytest


class TestSessionPersistence:
    """Tests for session persistence handler."""

    def test_extract_project_info_missing_file(self):
        from hooks.handlers.session_persistence import extract_project_info
        info = extract_project_info("/nonexistent/path")
        assert info["project_root"] is None
        assert info["files_modified"] == []

    def test_generate_memory_suggestions_no_project(self):
        from hooks.handlers.session_persistence import generate_memory_suggestions
        info = {
            "project_root": None,
            "technologies": [],
            "files_modified": [],
            "files_created": [],
            "tools_used": {}
        }
        result = generate_memory_suggestions(info)
        assert result["entities"] == []

    def test_cleanup_old_session_files_no_dir(self):
        from hooks.handlers.session_persistence import cleanup_old_session_files
        # Should not raise, just return 0
        result = cleanup_old_session_files(max_age_hours=24)
        assert isinstance(result, int)

"""Tests for batch_operation_detector functionality (now in tool_analytics)."""
import sys
from pathlib import Path

import pytest

from hooks.handlers.tool_analytics import (
    _batch_normalize_content as normalize_content,
    _batch_extract_pattern as extract_pattern,
    _batch_find_similar_edits as find_similar_edits,
    _batch_suggest_command as suggest_batch_command,
)


def get_file_extension(path: str) -> str:
    """Helper - get file extension."""
    return Path(path).suffix.lower()


class TestNormalizeContent:
    """Tests for content normalization."""

    def test_normalize_whitespace(self):
        """Should normalize whitespace."""
        assert normalize_content("hello   world") == "hello world"

    def test_normalize_newlines(self):
        """Should normalize newlines."""
        assert normalize_content("hello\n\nworld") == "hello world"

    def test_normalize_tabs(self):
        """Should normalize tabs."""
        assert normalize_content("hello\t\tworld") == "hello world"

    def test_normalize_case(self):
        """Should lowercase."""
        assert normalize_content("HELLO WORLD") == "hello world"

    def test_normalize_strip(self):
        """Should strip leading/trailing whitespace."""
        assert normalize_content("  hello  ") == "hello"


class TestExtractPattern:
    """Tests for pattern extraction."""

    def test_extract_basic_pattern(self):
        """Should extract basic pattern."""
        pattern = extract_pattern("old_name", "new_name")
        assert pattern["old_normalized"] == "old_name"
        assert pattern["new_normalized"] == "new_name"
        assert pattern["old_len"] == 8
        assert pattern["new_len"] == 8
        assert pattern["is_rename"] is True

    def test_extract_whitespace_only_change(self):
        """Should detect whitespace-only change."""
        pattern = extract_pattern("hello world", "helloworld")
        assert pattern["is_rename"] is False

    def test_extract_actual_change(self):
        """Should detect actual content change."""
        pattern = extract_pattern("foo", "bar")
        assert pattern["is_rename"] is True


class TestFindSimilarEdits:
    """Tests for finding similar edits."""

    def test_find_exact_old_match(self):
        """Should find edits with same old_normalized."""
        current = {"pattern": {"old_normalized": "foo", "new_normalized": "bar"}}
        history = [
            {"pattern": {"old_normalized": "foo", "new_normalized": "baz"}},
            {"pattern": {"old_normalized": "other", "new_normalized": "stuff"}},
        ]
        similar = find_similar_edits(current, history)
        assert len(similar) == 1

    def test_find_exact_new_match(self):
        """Should find edits with same new_normalized."""
        current = {"pattern": {"old_normalized": "different", "new_normalized": "bar"}}
        history = [
            {"pattern": {"old_normalized": "foo", "new_normalized": "bar"}},
        ]
        similar = find_similar_edits(current, history)
        assert len(similar) == 1

    def test_no_match(self):
        """Should return empty for no matches."""
        current = {"pattern": {"old_normalized": "unique", "new_normalized": "special"}}
        history = [
            {"pattern": {"old_normalized": "foo", "new_normalized": "bar"}},
        ]
        similar = find_similar_edits(current, history)
        assert len(similar) == 0

    def test_empty_history(self):
        """Should handle empty history."""
        current = {"pattern": {"old_normalized": "foo", "new_normalized": "bar"}}
        similar = find_similar_edits(current, [])
        assert len(similar) == 0


class TestGetFileExtension:
    """Tests for file extension extraction."""

    def test_python_extension(self):
        """Should get .py extension."""
        assert get_file_extension("/path/to/file.py") == ".py"

    def test_typescript_extension(self):
        """Should get .ts extension."""
        assert get_file_extension("src/component.ts") == ".ts"

    def test_no_extension(self):
        """Should return empty for no extension."""
        assert get_file_extension("Makefile") == ""

    def test_hidden_file(self):
        """Should handle hidden files."""
        assert get_file_extension(".gitignore") == ""

    def test_multiple_dots(self):
        """Should get last extension."""
        assert get_file_extension("file.test.js") == ".js"


class TestSuggestBatchCommand:
    """Tests for batch command suggestion."""

    def test_suggest_with_same_extension(self):
        """Should suggest glob for same extension."""
        edits = [
            {"file": "/project/src/a.py", "old_string": "foo", "new_string": "bar"},
            {"file": "/project/src/b.py", "old_string": "foo", "new_string": "bar"},
        ]
        current = {"file": "/project/src/c.py", "old_string": "foo", "new_string": "bar"}
        suggestion = suggest_batch_command(edits, current)
        assert ".py" in suggestion
        assert "foo" in suggestion or "bar" in suggestion

    def test_suggest_mixed_extensions(self):
        """Should handle mixed extensions."""
        edits = [
            {"file": "/project/a.py", "old_string": "x", "new_string": "y"},
            {"file": "/project/b.js", "old_string": "x", "new_string": "y"},
        ]
        current = {"file": "/project/c.ts", "old_string": "x", "new_string": "y"}
        suggestion = suggest_batch_command(edits, current)
        assert "/**/*" in suggestion  # Generic glob since mixed extensions

    def test_returns_string(self):
        """Should always return a string."""
        result = suggest_batch_command([], {"file": "test.py"})
        assert isinstance(result, str)

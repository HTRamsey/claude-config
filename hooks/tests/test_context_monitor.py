"""Tests for context_monitor module."""
import sys
from pathlib import Path

import pytest

from hooks.handlers.context_monitor import (
    TOKEN_WARNING_THRESHOLD,
    TOKEN_CRITICAL_THRESHOLD,
    count_tokens,
    get_cached_count,
    update_cache,
)


class TestTokenCounting:
    """Tests for token counting."""

    def test_count_tokens_empty(self):
        """Should return 0 for empty string."""
        assert count_tokens("") == 0

    def test_count_tokens_simple(self):
        """Should count tokens in simple text."""
        tokens = count_tokens("Hello world")
        assert tokens > 0
        assert tokens < 10  # Simple text should have few tokens

    def test_count_tokens_code(self):
        """Should count tokens in code."""
        code = """
def hello():
    print("Hello, world!")
    return True
"""
        tokens = count_tokens(code)
        assert tokens > 0


class TestThresholds:
    """Tests for token thresholds."""

    def test_warning_threshold_set(self):
        """Warning threshold should be defined."""
        assert TOKEN_WARNING_THRESHOLD > 0
        assert TOKEN_WARNING_THRESHOLD == 40000

    def test_critical_threshold_higher(self):
        """Critical threshold should be higher than warning."""
        assert TOKEN_CRITICAL_THRESHOLD > TOKEN_WARNING_THRESHOLD
        assert TOKEN_CRITICAL_THRESHOLD == 80000


class TestCaching:
    """Tests for cache functions."""

    def test_get_cached_count_missing(self, tmp_path):
        """Should return None for missing cache."""
        result = get_cached_count(str(tmp_path / "nonexistent.jsonl"))
        assert result is None

    def test_update_cache_runs(self, tmp_path):
        """update_cache should not raise."""
        test_file = tmp_path / "test.jsonl"
        test_file.write_text('{"test": true}\n')
        # Should not raise
        update_cache(str(test_file), 100, 5)

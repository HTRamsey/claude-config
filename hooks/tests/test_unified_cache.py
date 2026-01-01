"""Tests for unified_cache module."""
import json
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from unified_cache import (
    find_fuzzy_match,
    get_cache_key,
    load_cache,
    save_cache,
    handle_exploration_pre,
    handle_exploration_post,
    CacheConfig,
    CACHES,
)


class TestCacheKey:
    """Tests for cache key generation."""

    def test_cache_key_deterministic(self):
        """Same content should produce same key."""
        key1 = get_cache_key("test content")
        key2 = get_cache_key("test content")
        assert key1 == key2

    def test_cache_key_case_insensitive(self):
        """Keys should be case-insensitive."""
        key1 = get_cache_key("Test Content")
        key2 = get_cache_key("test content")
        assert key1 == key2

    def test_cache_key_different_content(self):
        """Different content should produce different keys."""
        key1 = get_cache_key("content a")
        key2 = get_cache_key("content b")
        assert key1 != key2

    def test_cache_key_length(self):
        """Cache key should be 16 chars (truncated MD5)."""
        key = get_cache_key("any content")
        assert len(key) == 16


class TestFuzzyMatch:
    """Tests for fuzzy matching."""

    @pytest.fixture
    def cache_config(self):
        """Return exploration cache config."""
        return CACHES["exploration"]

    @pytest.fixture
    def sample_cache(self):
        """Return cache with sample entries."""
        now = time.time()
        return {
            "entries": {
                "key1": {
                    "prompt": "find config files",
                    "summary": "Found 5 config files",
                    "cwd": "/project",
                    "timestamp": now - 60
                },
                "key2": {
                    "prompt": "search for authentication",
                    "summary": "Found auth module",
                    "cwd": "/project",
                    "timestamp": now - 120
                },
                "key3": {
                    "prompt": "list all files",
                    "summary": "Listed files",
                    "cwd": "/other",
                    "timestamp": now - 30
                }
            }
        }

    def test_fuzzy_match_exact(self, sample_cache, cache_config):
        """Should find exact match."""
        result = find_fuzzy_match("find config files", "/project", sample_cache, cache_config)
        assert result is not None
        assert result["prompt"] == "find config files"

    def test_fuzzy_match_similar(self, sample_cache, cache_config):
        """Should find similar match."""
        result = find_fuzzy_match("find configuration files", "/project", sample_cache, cache_config)
        assert result is not None
        assert "config" in result["prompt"]

    def test_fuzzy_match_respects_cwd(self, sample_cache, cache_config):
        """Should only match entries from same cwd."""
        result = find_fuzzy_match("list all files", "/project", sample_cache, cache_config)
        # Entry exists but in /other cwd
        assert result is None

    def test_fuzzy_match_no_match(self, sample_cache, cache_config):
        """Should return None for no match."""
        result = find_fuzzy_match("completely different query", "/project", sample_cache, cache_config)
        assert result is None

    def test_fuzzy_match_expired_entries(self, cache_config):
        """Should not match expired entries."""
        expired_cache = {
            "entries": {
                "key1": {
                    "prompt": "find files",
                    "cwd": "/project",
                    "timestamp": time.time() - 999999  # Very old
                }
            }
        }
        result = find_fuzzy_match("find files", "/project", expired_cache, cache_config)
        assert result is None


class TestCacheLoadSave:
    """Tests for cache load/save operations."""

    def test_load_cache_empty(self, tmp_path):
        """Should return empty cache for missing file."""
        cfg = CacheConfig(
            name="test",
            file=tmp_path / "test.json",
            ttl_seconds=3600,
            max_entries=100
        )
        cache = load_cache(cfg)
        assert cache == {"entries": {}, "stats": {"hits": 0, "misses": 0, "saves": 0}}

    def test_save_load_roundtrip(self, tmp_path):
        """Cache should roundtrip through save/load."""
        cfg = CacheConfig(
            name="test",
            file=tmp_path / "test.json",
            ttl_seconds=3600,
            max_entries=100
        )
        cache = {
            "entries": {"key1": {"prompt": "test", "timestamp": time.time()}},
            "stats": {"hits": 5, "misses": 3, "saves": 8}
        }
        save_cache(cfg, cache)
        loaded = load_cache(cfg)
        assert loaded["entries"]["key1"]["prompt"] == "test"
        assert loaded["stats"]["hits"] == 5

    def test_save_cache_limits_size(self, tmp_path):
        """Should limit cache to max_entries."""
        cfg = CacheConfig(
            name="test",
            file=tmp_path / "test.json",
            ttl_seconds=3600,
            max_entries=2
        )
        now = time.time()
        cache = {
            "entries": {
                "key1": {"prompt": "old", "timestamp": now - 100},
                "key2": {"prompt": "medium", "timestamp": now - 50},
                "key3": {"prompt": "new", "timestamp": now - 10},
            },
            "stats": {}
        }
        save_cache(cfg, cache)
        loaded = load_cache(cfg)
        assert len(loaded["entries"]) == 2
        # Should keep newest entries
        assert "key3" in loaded["entries"]


class TestExplorationHandlers:
    """Tests for exploration pre/post handlers."""

    def test_exploration_pre_ignores_non_explore(self):
        """Should ignore non-Explore agents."""
        ctx = {
            "tool_name": "Task",
            "tool_input": {"subagent_type": "code-reviewer", "prompt": "review code"}
        }
        result = handle_exploration_pre(ctx)
        assert result is None

    def test_exploration_post_ignores_non_explore(self):
        """Should ignore non-Explore agents."""
        ctx = {
            "tool_name": "Task",
            "tool_input": {"subagent_type": "batch-editor", "prompt": "edit files"},
            "tool_response": "Edited 3 files"
        }
        result = handle_exploration_post(ctx)
        assert result is None

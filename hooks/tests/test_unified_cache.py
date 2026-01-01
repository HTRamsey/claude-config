"""Tests for unified_cache module (diskcache implementation)."""
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from diskcache import Cache

from hooks.handlers.unified_cache import (
    find_fuzzy_match,
    get_cache_key,
    get_exploration_entry,
    save_exploration_entry,
    get_research_entry,
    save_research_entry,
    handle_exploration_pre,
    handle_exploration_post,
    handle_research_pre,
    handle_research_post,
    CacheConfig,
    CACHE_CONFIGS,
    _caches,
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


@pytest.fixture
def test_cache(tmp_path):
    """Create a temporary test cache."""
    cache = Cache(str(tmp_path / "test-cache"))
    yield cache
    cache.close()


@pytest.fixture
def exploration_config():
    """Return exploration cache config."""
    return CACHE_CONFIGS["exploration"]


@pytest.fixture
def research_config():
    """Return research cache config."""
    return CACHE_CONFIGS["research"]


@pytest.fixture
def mock_caches(tmp_path):
    """Mock the _caches dict with temporary caches."""
    exploration_cache = Cache(str(tmp_path / "exploration"))
    research_cache = Cache(str(tmp_path / "research"))
    stats_cache = Cache(str(tmp_path / "stats"))

    mock_caches = {
        "exploration": exploration_cache,
        "research": research_cache,
        "stats": stats_cache,
    }

    with patch.dict('hooks.handlers.unified_cache._caches', mock_caches, clear=True):
        with patch('hooks.handlers.unified_cache._get_cache', side_effect=lambda name: mock_caches.get(name)):
            with patch('hooks.handlers.unified_cache._get_stats_cache', return_value=stats_cache):
                yield mock_caches

    exploration_cache.close()
    research_cache.close()
    stats_cache.close()


class TestExplorationCache:
    """Tests for exploration cache operations."""

    def test_save_and_get_entry(self, mock_caches, exploration_config):
        """Should save and retrieve exploration entry."""
        cache_key = get_cache_key("/project:find files")
        entry = {
            "prompt": "find files",
            "summary": "Found 5 files",
            "cwd": "/project",
            "timestamp": time.time(),
            "subagent": "Explore"
        }
        save_exploration_entry(cache_key, entry, exploration_config)

        result = get_exploration_entry(cache_key, exploration_config)
        assert result is not None
        assert result["prompt"] == "find files"
        assert result["summary"] == "Found 5 files"

    def test_get_expired_entry_returns_none(self, mock_caches, exploration_config):
        """Should not return expired entries."""
        cache_key = get_cache_key("/project:old query")
        # Insert with old timestamp
        entry = {
            "prompt": "old query",
            "summary": "old result",
            "cwd": "/project",
            "timestamp": time.time() - exploration_config.ttl_seconds - 100,
            "subagent": "Explore"
        }
        mock_caches["exploration"].set(cache_key, entry)

        result = get_exploration_entry(cache_key, exploration_config)
        assert result is None


class TestResearchCache:
    """Tests for research cache operations."""

    def test_save_and_get_entry(self, mock_caches, research_config):
        """Should save and retrieve research entry."""
        url = "https://example.com/docs"
        cache_key = get_cache_key(url)
        entry = {
            "url": url,
            "summary": "Documentation content",
            "timestamp": time.time()
        }
        save_research_entry(cache_key, entry, research_config)

        result = get_research_entry(cache_key, research_config)
        assert result is not None
        assert result["url"] == url
        assert result["summary"] == "Documentation content"


class TestFuzzyMatch:
    """Tests for fuzzy matching."""

    def test_fuzzy_match_similar(self, mock_caches, exploration_config):
        """Should find similar match."""
        now = time.time()

        # Insert test data directly into cache
        entry = {
            "prompt": "find config files",
            "summary": "Found configs",
            "cwd": "/project",
            "timestamp": now - 60,
            "subagent": "Explore"
        }
        mock_caches["exploration"].set("key1", entry)

        result = find_fuzzy_match("find configuration files", "/project", exploration_config)
        assert result is not None
        assert "config" in result["prompt"]

    def test_fuzzy_match_respects_cwd(self, mock_caches, exploration_config):
        """Should only match entries from same cwd."""
        now = time.time()

        # Insert entry in different cwd
        entry = {
            "prompt": "list all files",
            "summary": "Listed files",
            "cwd": "/other",
            "timestamp": now - 30,
            "subagent": "Explore"
        }
        mock_caches["exploration"].set("key1", entry)

        result = find_fuzzy_match("list all files", "/project", exploration_config)
        assert result is None

    def test_fuzzy_match_no_match(self, mock_caches, exploration_config):
        """Should return None for no match."""
        now = time.time()

        entry = {
            "prompt": "find config files",
            "summary": "Found configs",
            "cwd": "/project",
            "timestamp": now - 60,
            "subagent": "Explore"
        }
        mock_caches["exploration"].set("key1", entry)

        result = find_fuzzy_match("completely different query about authentication", "/project", exploration_config)
        assert result is None


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
            "tool_result": {"content": "Edited 3 files"}
        }
        result = handle_exploration_post(ctx)
        assert result is None

    def test_exploration_pre_ignores_empty_prompt(self):
        """Should ignore empty prompts."""
        ctx = {
            "tool_name": "Task",
            "tool_input": {"subagent_type": "Explore", "prompt": ""}
        }
        result = handle_exploration_pre(ctx)
        assert result is None


class TestResearchHandlers:
    """Tests for research pre/post handlers."""

    def test_research_pre_ignores_no_url(self):
        """Should ignore requests without URL."""
        ctx = {
            "tool_name": "WebFetch",
            "tool_input": {}
        }
        result = handle_research_pre(ctx)
        assert result is None

    def test_research_post_ignores_empty_content(self):
        """Should ignore empty responses."""
        ctx = {
            "tool_name": "WebFetch",
            "tool_input": {"url": "https://example.com"},
            "tool_result": {"content": ""}
        }
        result = handle_research_post(ctx)
        assert result is None

    def test_research_post_ignores_large_content(self):
        """Should ignore very large responses."""
        ctx = {
            "tool_name": "WebFetch",
            "tool_input": {"url": "https://example.com"},
            "tool_result": {"content": "x" * 60000}  # Over 50KB limit
        }
        result = handle_research_post(ctx)
        assert result is None


class TestCacheConfig:
    """Tests for CacheConfig dataclass."""

    def test_exploration_config_has_fuzzy(self):
        """Exploration cache should have fuzzy matching enabled."""
        cfg = CACHE_CONFIGS["exploration"]
        assert cfg.fuzzy_match is True
        assert cfg.similarity_threshold == 0.6

    def test_research_config_no_fuzzy(self):
        """Research cache should not have fuzzy matching."""
        cfg = CACHE_CONFIGS["research"]
        assert cfg.fuzzy_match is False

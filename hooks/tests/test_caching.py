"""Tests for TTLCachedLoader utility."""
import pytest
import time
from unittest.mock import Mock
from hooks.hook_utils.state import TTLCachedLoader


def test_ttl_cached_loader_returns_cached_value():
    """TTLCachedLoader returns cached value on second call."""
    load_func = Mock(return_value={"data": "test"})
    loader = TTLCachedLoader(
        load_func=load_func,
        cache_key="test_key",
        ttl=60.0
    )

    # First call loads fresh
    result1 = loader.get()
    assert result1 == {"data": "test"}
    assert load_func.call_count == 1

    # Second call uses cache
    result2 = loader.get()
    assert result2 == {"data": "test"}
    assert load_func.call_count == 1  # Not called again


def test_ttl_cached_loader_invalidate():
    """TTLCachedLoader.invalidate clears cache."""
    load_func = Mock(return_value={"data": "test"})
    loader = TTLCachedLoader(
        load_func=load_func,
        cache_key="test_key",
        ttl=60.0
    )

    # Load and cache
    loader.get()
    assert load_func.call_count == 1

    # Invalidate
    loader.invalidate()

    # Next get reloads
    loader.get()
    assert load_func.call_count == 2


def test_ttl_cached_loader_refresh():
    """TTLCachedLoader.refresh forces reload."""
    load_func = Mock(return_value={"data": "test"})
    loader = TTLCachedLoader(
        load_func=load_func,
        cache_key="test_key",
        ttl=60.0
    )

    # Load and cache
    loader.get()
    assert load_func.call_count == 1

    # Refresh
    result = loader.refresh()
    assert result == {"data": "test"}
    assert load_func.call_count == 2


def test_ttl_cached_loader_ttl_expiration():
    """TTLCachedLoader expires entries after TTL."""
    load_func = Mock(return_value={"data": "test"})
    loader = TTLCachedLoader(
        load_func=load_func,
        cache_key="test_key",
        ttl=0.1  # 100ms TTL
    )

    # Load and cache
    loader.get()
    assert load_func.call_count == 1

    # Wait for TTL expiration
    time.sleep(0.15)

    # Next get reloads (entry expired)
    loader.get()
    assert load_func.call_count == 2


def test_ttl_cached_loader_multiple_keys():
    """TTLCachedLoader handles multiple cache keys."""
    load_func1 = Mock(return_value={"data": "first"})
    load_func2 = Mock(return_value={"data": "second"})

    loader1 = TTLCachedLoader(
        load_func=load_func1,
        cache_key="key1",
        ttl=60.0,
        maxsize=10
    )
    loader2 = TTLCachedLoader(
        load_func=load_func2,
        cache_key="key2",
        ttl=60.0,
        maxsize=10
    )

    # Each loader maintains separate cache
    result1 = loader1.get()
    result2 = loader2.get()

    assert result1 == {"data": "first"}
    assert result2 == {"data": "second"}
    assert load_func1.call_count == 1
    assert load_func2.call_count == 1

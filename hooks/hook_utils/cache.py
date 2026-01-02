"""
Cache abstraction layer.

Provides a unified interface for TTL caching, currently backed by cachetools.
Allows easy swapping of cache implementations (redis, diskcache, etc.) in the future.
"""
from typing import TypeVar, Callable, Any
from cachetools import TTLCache, LRUCache

T = TypeVar('T')


def create_ttl_cache(maxsize: int = 100, ttl: float = 300) -> TTLCache:
    """
    Create a TTL cache with automatic expiration.

    Args:
        maxsize: Maximum number of items in cache
        ttl: Time-to-live in seconds (default: 5 minutes)

    Returns:
        TTLCache instance

    Example:
        cache = create_ttl_cache(maxsize=50, ttl=60)
        cache["key"] = "value"
        value = cache.get("key")
    """
    return TTLCache(maxsize=maxsize, ttl=ttl)


def create_lru_cache(maxsize: int = 100) -> LRUCache:
    """
    Create an LRU cache (no TTL, evicts least recently used).

    Args:
        maxsize: Maximum number of items in cache

    Returns:
        LRUCache instance
    """
    return LRUCache(maxsize=maxsize)


def cached_call(cache: Any, key: str, loader: Callable[[], T], default: T = None) -> T:
    """
    Get value from cache or load it.

    Args:
        cache: Cache instance (TTLCache, LRUCache, or dict-like)
        key: Cache key
        loader: Function to call if key not in cache
        default: Default value if loader fails

    Returns:
        Cached or freshly loaded value

    Example:
        cache = create_ttl_cache()
        value = cached_call(cache, "my_key", lambda: expensive_computation())
    """
    try:
        return cache[key]
    except KeyError:
        try:
            value = loader()
            cache[key] = value
            return value
        except Exception:
            return default

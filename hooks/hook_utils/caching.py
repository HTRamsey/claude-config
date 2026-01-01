"""Unified caching utilities with TTL support."""
import threading
from typing import TypeVar, Generic, Callable
from cachetools import TTLCache

T = TypeVar('T')


class TTLCachedLoader(Generic[T]):
    """
    Generic TTL-cached loader for disk-backed data.

    Combines TTLCache with thread-safe locking for safe concurrent access.
    Automatically expires entries and evicts LRU entries when maxsize exceeded.

    Usage:
        loader = TTLCachedLoader(
            load_func=lambda: safe_load_json(path, {}),
            cache_key="my_data",
            ttl=60.0,
            maxsize=10
        )
        data = loader.get()  # Returns cached or loads fresh
        loader.invalidate()  # Clear cache
        fresh = loader.refresh()  # Force reload

    Type Parameters:
        T: The type of data being cached

    Thread Safety:
        All operations are protected by an internal lock.
    """

    def __init__(
        self,
        load_func: Callable[[], T],
        cache_key: str,
        ttl: float = 60.0,
        maxsize: int = 10
    ):
        """
        Initialize TTL-cached loader.

        Args:
            load_func: Callable that loads fresh data (called on cache miss)
            cache_key: Key to use in the cache
            ttl: Time-to-live in seconds (after which entry expires)
            maxsize: Maximum number of entries before LRU eviction
        """
        self.load_func = load_func
        self.cache_key = cache_key
        self._cache: TTLCache = TTLCache(maxsize=maxsize, ttl=ttl)
        self._lock = threading.Lock()

    def get(self) -> T:
        """
        Get cached value or load fresh.

        Returns cached value if still valid (within TTL).
        Otherwise loads fresh data and caches it.

        Returns:
            Cached or newly loaded data
        """
        with self._lock:
            if self.cache_key in self._cache:
                return self._cache[self.cache_key]
            data = self.load_func()
            self._cache[self.cache_key] = data
            return data

    def invalidate(self) -> None:
        """Clear the cache (forces reload on next get)."""
        with self._lock:
            self._cache.clear()

    def refresh(self) -> T:
        """
        Force reload and cache.

        Invalidates current cache and immediately loads fresh data.

        Returns:
            Newly loaded data
        """
        self.invalidate()
        return self.get()

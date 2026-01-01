"""
Global state management with caching and batch writes.

Uses cachetools TTLCache for automatic expiration and thread-safe access.
Supports batched writes to reduce disk I/O during dispatch.
"""
import threading
import time
from typing import Callable, TypeVar, Generic

from cachetools import TTLCache

T = TypeVar('T')

from .io import safe_load_json, atomic_write_json
from .logging import DATA_DIR

# Import centralized config
try:
    from config import Timeouts
    CACHE_TTL = Timeouts.CACHE_TTL
except ImportError:
    CACHE_TTL = 5.0  # Fallback

# Thread-safe TTL cache for state files
_cache: TTLCache = TTLCache(maxsize=100, ttl=CACHE_TTL)
_cache_lock = threading.Lock()

# Pending writes for batch flushing (reduces disk I/O during dispatch)
_pending_writes: dict[str, dict] = {}
_pending_lock = threading.Lock()


def read_state(name: str, default: dict = None) -> dict:
    """
    Read state file with caching.

    Args:
        name: State file name (without .json extension)
        default: Default value if file doesn't exist

    Returns:
        State dict (cached for CACHE_TTL seconds)
    """
    if default is None:
        default = {}

    with _cache_lock:
        if name in _cache:
            return _cache[name].copy()

    path = DATA_DIR / f"{name}.json"
    data = safe_load_json(path, default)

    with _cache_lock:
        _cache[name] = data.copy()

    return data


def write_state(name: str, data: dict) -> bool:
    """
    Write state file atomically with cache update.

    Args:
        name: State file name (without .json extension)
        data: Data to write

    Returns:
        True on success
    """
    path = DATA_DIR / f"{name}.json"
    success = atomic_write_json(path, data)
    if success:
        with _cache_lock:
            _cache[name] = data.copy()
    return success


def update_state(name: str, updater: Callable[[dict], dict], default: dict = None) -> bool:
    """
    Read-modify-write pattern with caching.

    Args:
        name: State file name
        updater: Function that takes current state and returns updated state
        default: Default state if file doesn't exist

    Returns:
        True on success
    """
    data = read_state(name, default)
    updated = updater(data)
    return write_state(name, updated)


def flush_pending_writes() -> int:
    """
    Flush all pending state writes to disk.

    Returns:
        Number of files successfully written
    """
    with _pending_lock:
        pending = _pending_writes.copy()
        _pending_writes.clear()

    count = 0
    for name, data in pending.items():
        path = DATA_DIR / f"{name}.json"
        if atomic_write_json(path, data):
            count += 1

    return count


# =============================================================================
# TTLCachedLoader - Generic TTL-cached loader
# =============================================================================

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

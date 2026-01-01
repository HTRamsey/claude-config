"""
Global state management with caching and batch writes.

Uses cachetools TTLCache for automatic expiration and thread-safe access.
Supports batched writes to reduce disk I/O during dispatch.
"""
import threading
from typing import Callable

from cachetools import TTLCache

from .io import safe_load_json, atomic_write_json
from .logging import DATA_DIR

# Standard TTL Constants
CACHE_TTL = 5.0  # In-memory cache default (seconds)

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


def invalidate_cache(name: str = None):
    """Invalidate cache for a state file or all files."""
    with _cache_lock:
        if name:
            _cache.pop(name, None)
        else:
            _cache.clear()


# =============================================================================
# Batch Write API (for dispatcher optimization)
# =============================================================================

def queue_state_write(name: str, data: dict):
    """
    Queue a state write for batch flushing later.

    Updates in-memory cache immediately (for reads) but defers disk write.
    Call flush_pending_writes() at the end of dispatch to persist.

    Args:
        name: State file name (without .json extension)
        data: Data to queue for writing
    """
    with _pending_lock:
        _pending_writes[name] = data.copy()
    # Update cache immediately so reads see the new data
    with _cache_lock:
        _cache[name] = data.copy()


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


def has_pending_writes() -> bool:
    """Check if there are pending writes queued."""
    with _pending_lock:
        return len(_pending_writes) > 0


def update_state_batched(name: str, updater: Callable[[dict], dict], default: dict = None):
    """
    Read-modify-write pattern with batched write.

    Same as update_state() but queues the write instead of writing immediately.
    Call flush_pending_writes() at the end of dispatch.

    Args:
        name: State file name
        updater: Function that takes current state and returns updated state
        default: Default state if file doesn't exist
    """
    data = read_state(name, default)
    updated = updater(data)
    queue_state_write(name, updated)

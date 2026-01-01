"""
Global state management with caching and batch writes.

Uses cachetools TTLCache for automatic expiration and thread-safe access.
Supports batched writes to reduce disk I/O during dispatch.
"""
import threading
import time
from typing import Callable

from cachetools import TTLCache

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


# =============================================================================
# Pruning Utilities
# =============================================================================

def prune_by_time(
    items: dict,
    max_age_secs: float,
    time_key: str = "timestamp",
    now: float = None
) -> dict:
    """Keep only items newer than max_age_secs.

    Args:
        items: Dict of {key: {time_key: timestamp, ...}}
        max_age_secs: Maximum age in seconds
        time_key: Key containing timestamp in each item
        now: Current time (defaults to time.time())

    Returns:
        Pruned dict with only items newer than cutoff time
    """
    if now is None:
        now = time.time()
    cutoff = now - max_age_secs
    return {k: v for k, v in items.items() if v.get(time_key, 0) > cutoff}


# =============================================================================
# StateManager - Unified State Management
# =============================================================================

class StateManager:
    """Unified state management with TTL and pruning support.

    Consolidates patterns used across 5 hooks:
    - file_monitor: session state with TTL and pruning
    - tdd_guard: simple global state
    - state_saver: global state with timestamps
    - tool_analytics: session state with age checks
    - unified_cache: file-based caching with TTL

    Usage:
        # Session-based state with TTL
        sm = StateManager(namespace="file_monitor", use_session=True)
        state = sm.load_with_ttl(session_id="abc123", max_age_secs=86400)
        sm.save_with_pruning(state, session_id="abc123", max_entries=100)

        # Global state
        sm = StateManager(namespace="tdd-warnings", use_session=False)
        state = sm.load_with_ttl()
        sm.save_with_pruning(state, max_entries=50)
    """

    def __init__(self, namespace: str, use_session: bool = True):
        """Initialize state manager.

        Args:
            namespace: State namespace/key (e.g., "file_monitor", "tdd-warnings")
            use_session: Use session-based storage (True) or global (False)
        """
        self.namespace = namespace
        self.use_session = use_session

    def load_with_ttl(
        self,
        session_id: str = None,
        default: dict = None,
        max_age_secs: int = None,
        time_key: str = "last_update"
    ) -> dict:
        """Load state with automatic expiry check.

        Common pattern: Load state but return default if too old.

        Args:
            session_id: Session ID (required if use_session=True)
            default: Default state if missing or expired
            max_age_secs: Max age in seconds before expiry (no check if None)
            time_key: Key in state dict containing last update timestamp

        Returns:
            State dict (loaded or default copy)
        """
        if default is None:
            default = {}

        if self.use_session:
            from .session import read_session_state
            state = read_session_state(self.namespace, session_id, default)
        else:
            state = read_state(self.namespace, default)

        if max_age_secs is None:
            return state

        # Check age
        current_time = time.time()
        last_update = state.get(time_key, 0)
        if current_time - last_update > max_age_secs:
            return default.copy()

        return state

    def save_with_pruning(
        self,
        state: dict,
        session_id: str = None,
        max_entries: int = None,
        items_key: str = None,
        time_key: str = "timestamp"
    ) -> bool:
        """Save state with optional pruning of old entries.

        Common pattern: Save state and limit size by keeping newest entries.

        Args:
            state: State dict to save
            session_id: Session ID (required if use_session=True)
            max_entries: Max number of entries to keep in items dict (no limit if None)
            items_key: Key in state containing items to prune (e.g., "reads", "searches")
                      If None, no pruning is performed
            time_key: Key in each item containing timestamp (used for pruning order)

        Returns:
            True on success
        """
        # Prune items if needed
        if max_entries and items_key and items_key in state:
            items = state.get(items_key, {})
            if len(items) > max_entries:
                sorted_items = sorted(
                    items.items(),
                    key=lambda x: x[1].get(time_key, 0),
                    reverse=True
                )
                state[items_key] = dict(sorted_items[:max_entries])

        # Add timestamp to state
        state["last_update"] = time.time()

        # Save
        if self.use_session:
            from .session import write_session_state
            return write_session_state(self.namespace, state, session_id)
        else:
            return write_state(self.namespace, state)

    def update(
        self,
        updater: Callable[[dict], dict],
        session_id: str = None,
        default: dict = None
    ) -> bool:
        """Read-modify-write pattern.

        Args:
            updater: Function that takes current state and returns updated state
            session_id: Session ID (required if use_session=True)
            default: Default state if missing

        Returns:
            True on success
        """
        state = self.load_with_ttl(session_id, default)
        updated = updater(state)
        return self.save_with_pruning(updated, session_id)

    def load_raw(self, session_id: str = None, default: dict = None) -> dict:
        """Load state without any TTL/expiry checks.

        Args:
            session_id: Session ID (required if use_session=True)
            default: Default state if missing

        Returns:
            Raw state dict
        """
        if default is None:
            default = {}

        if self.use_session:
            from .session import read_session_state
            return read_session_state(self.namespace, session_id, default)
        else:
            return read_state(self.namespace, default)

    def save_raw(self, state: dict, session_id: str = None) -> bool:
        """Save state without any modifications.

        Args:
            state: State dict to save
            session_id: Session ID (required if use_session=True)

        Returns:
            True on success
        """
        if self.use_session:
            from .session import write_session_state
            return write_session_state(self.namespace, state, session_id)
        else:
            return write_state(self.namespace, state)

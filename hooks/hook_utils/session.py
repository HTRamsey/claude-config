"""
Session-aware state management.

Uses cachetools for automatic TTL expiration and LRU eviction.
"""
import hashlib
import json
import os
import threading
import time
from pathlib import Path
from typing import Callable

from cachetools import TTLCache, LRUCache

from .io import safe_load_json, atomic_write_json, file_lock
from .logging import DATA_DIR, ensure_data_dir
from .metrics import get_timestamp

# Import centralized config
try:
    from config import Timeouts, SESSION_STATE_DIR, SESSION_STATE_FILE
    CACHE_TTL = Timeouts.CACHE_TTL
    SESSION_STATE_MAX_AGE = Timeouts.STATE_MAX_AGE  # 24 hours
except ImportError:
    SESSION_STATE_DIR = DATA_DIR / "sessions"
    SESSION_STATE_FILE = DATA_DIR / "session-state.json"
    SESSION_STATE_MAX_AGE = 3600 * 24
    CACHE_TTL = 5.0

# TTL cache for session state (expires after CACHE_TTL seconds)
_session_cache: TTLCache = TTLCache(maxsize=50, ttl=CACHE_TTL)
_session_cache_lock = threading.Lock()

# LRU cache for computed session IDs (no TTL needed - pure function memoization)
_session_id_cache: LRUCache = LRUCache(maxsize=100)
_session_id_lock = threading.Lock()


def get_session_id(ctx: dict = None, transcript_path: str = None) -> str:
    """
    Get consistent session ID from context or generate one.

    Priority:
        1. ctx["session_id"] if available
        2. CLAUDE_SESSION_ID environment variable
        3. Hash of transcript_path if provided (cached)
        4. "default" as final fallback
    """
    if ctx and ctx.get("session_id"):
        return ctx["session_id"]

    session_from_env = os.environ.get("CLAUDE_SESSION_ID")
    if session_from_env:
        return session_from_env

    path = transcript_path or (ctx.get("transcript_path") if ctx else None)
    if path:
        # Check cache first to avoid repeated MD5 computation
        with _session_id_lock:
            if path in _session_id_cache:
                return _session_id_cache[path]
            session_id = hashlib.md5(path.encode()).hexdigest()[:8]
            _session_id_cache[path] = session_id
            return session_id

    return "default"


def is_new_session(ctx: dict = None, transcript_path: str = None) -> bool:
    """Check if this is a new session (first message).

    Uses atomic_write_json to avoid race conditions where
    the file is truncated before acquiring the lock.
    """
    try:
        ensure_data_dir()
        session_id = get_session_id(ctx, transcript_path)

        state = safe_load_json(SESSION_STATE_FILE, {})
        seen_sessions = state.get("seen_sessions", [])

        if session_id not in seen_sessions:
            seen_sessions.append(session_id)
            state["seen_sessions"] = seen_sessions[-100:]
            state["last_session"] = session_id
            state["last_session_start"] = get_timestamp()

            atomic_write_json(SESSION_STATE_FILE, state)
            return True

        return False
    except Exception:
        return False


def get_session_state() -> dict:
    """Get current session state."""
    try:
        if SESSION_STATE_FILE.exists():
            with open(SESSION_STATE_FILE) as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _get_session_state_file(session_id: str) -> Path:
    """Get session state file path, creating directory if needed."""
    SESSION_STATE_DIR.mkdir(parents=True, exist_ok=True)
    return SESSION_STATE_DIR / f"{session_id}.json"


def read_session_state(namespace: str, session_id: str = None, default: dict = None) -> dict:
    """
    Read namespaced state for a session.

    Args:
        namespace: State namespace (e.g., "batch_detector", "file_monitor")
        session_id: Session ID (auto-detected if not provided)
        default: Default value if state doesn't exist
    """
    if default is None:
        default = {}

    if not session_id:
        session_id = get_session_id()  # Use centralized session ID retrieval

    if not session_id or session_id == "default":
        return default.copy()

    cache_key = f"session:{session_id}"

    with _session_cache_lock:
        if cache_key in _session_cache:
            cached_data = _session_cache[cache_key]
            return cached_data.get("namespaces", {}).get(namespace, default).copy()

    state_file = _get_session_state_file(session_id)
    session_data = safe_load_json(state_file, {"namespaces": {}, "updated": time.time()})

    with _session_cache_lock:
        _session_cache[cache_key] = session_data

    return session_data.get("namespaces", {}).get(namespace, default).copy()


def write_session_state(namespace: str, data: dict, session_id: str = None) -> bool:
    """
    Write namespaced state for a session.
    """
    if not session_id:
        session_id = get_session_id()  # Use centralized session ID retrieval

    if not session_id or session_id == "default":
        return False

    state_file = _get_session_state_file(session_id)
    now = time.time()

    session_data = safe_load_json(state_file, {"namespaces": {}, "updated": now})
    session_data["namespaces"][namespace] = data
    session_data["updated"] = now

    success = atomic_write_json(state_file, session_data)

    if success:
        cache_key = f"session:{session_id}"
        with _session_cache_lock:
            _session_cache[cache_key] = session_data

    return success


def update_session_state(
    namespace: str,
    updater: Callable[[dict], dict],
    session_id: str = None,
    default: dict = None
) -> bool:
    """Read-modify-write pattern for session state."""
    data = read_session_state(namespace, session_id, default)
    updated = updater(data)
    return write_session_state(namespace, updated, session_id)


def cleanup_old_sessions(max_age_secs: int = SESSION_STATE_MAX_AGE):
    """Remove session state files older than max_age_secs."""
    if not SESSION_STATE_DIR.exists():
        return

    now = time.time()
    cutoff = now - max_age_secs

    for state_file in SESSION_STATE_DIR.glob("*.json"):
        try:
            if state_file.stat().st_mtime < cutoff:
                state_file.unlink()
        except (IOError, OSError):
            pass


def load_state_with_expiry(
    namespace: str,
    session_id: str,
    default: dict,
    max_age_secs: int,
    time_key: str = "last_update"
) -> dict:
    """
    Load session state with automatic expiry check.

    Common pattern used by file_monitor, batch_operation_detector, etc.
    Returns default if state is older than max_age_secs.

    Args:
        namespace: State namespace
        session_id: Session identifier
        default: Default state to return if missing or expired
        max_age_secs: Maximum age in seconds before state expires
        time_key: Key in state dict containing last update timestamp

    Returns:
        State dict (either loaded or default copy)
    """
    state = read_session_state(namespace, session_id, default)
    if time.time() - state.get(time_key, 0) > max_age_secs:
        return default.copy()
    return state


def save_state_with_timestamp(
    namespace: str,
    state: dict,
    session_id: str,
    time_key: str = "last_update"
) -> bool:
    """
    Save session state with automatic timestamp update.

    Args:
        namespace: State namespace
        state: State dict to save
        session_id: Session identifier
        time_key: Key to use for timestamp

    Returns:
        True if save succeeded
    """
    state[time_key] = time.time()
    return write_session_state(namespace, state, session_id)

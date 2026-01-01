"""
Shared state and utilities for suggestion modules.
"""
import json
import threading
from pathlib import Path

from hooks.config import DATA_DIR, CACHE_DIR, Limits

CACHE_DIR.mkdir(parents=True, exist_ok=True)
SUGGESTION_CACHE = CACHE_DIR / "suggestion-engine-cache.json"

# Thread-safe state access with dirty flag
_state = None
_state_dirty = False
_state_lock = threading.Lock()


def get_state() -> dict:
    """Load or initialize shared suggestion state (thread-safe)."""
    global _state
    with _state_lock:
        if _state is not None:
            return _state.copy()
        try:
            if SUGGESTION_CACHE.exists():
                with open(SUGGESTION_CACHE) as f:
                    _state = json.load(f)
            else:
                _state = {}
        except Exception:
            _state = {}
        return _state.copy()


def update_state(updates: dict):
    """Update state with new values (thread-safe). Marks state as dirty."""
    global _state, _state_dirty
    with _state_lock:
        if _state is None:
            _state = {}
        _state.update(updates)
        _state_dirty = True


def save_state():
    """Persist state to disk with size limits. Only writes if state is dirty."""
    global _state, _state_dirty
    with _state_lock:
        if _state is None or not _state_dirty:
            return
        try:
            state_copy = _state.copy()
            # Prune state to prevent unbounded growth
            if "skills_suggested" in state_copy:
                state_copy["skills_suggested"] = list(state_copy["skills_suggested"])[-Limits.MAX_SUGGESTED_SKILLS:]
            if "recent_patterns" in state_copy:
                state_copy["recent_patterns"] = state_copy["recent_patterns"][-Limits.MAX_RECENT_PATTERNS:]
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            with open(SUGGESTION_CACHE, "w") as f:
                json.dump(state_copy, f)
            _state_dirty = False
        except Exception:
            pass

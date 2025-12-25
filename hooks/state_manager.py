#!/home/jonglaser/.claude/venv/bin/python3
"""
Unified State Manager - Centralized state handling for all hooks.

Provides:
- Atomic file writes (temp + rename)
- File locking for concurrent access
- Lazy loading with caching
- Schema validation
- Single interface for all state operations

State files managed:
- checkpoint-state.json: Checkpoint tracking
- session-history.json: Session metadata
- usage-stats.json: Agent/skill/command usage
- permission-patterns.json: Learned permission patterns
- exploration-cache.json: Cached codebase explorations
- research-cache.json: Cached web research
- token-usage.json: Daily token tracking
"""
import json
import os
import tempfile
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

# Data directory
DATA_DIR = Path.home() / ".claude" / "data"

# File locks for thread safety
_locks: dict[str, threading.Lock] = {}
_lock_lock = threading.Lock()

# In-memory cache
_cache: dict[str, tuple[float, Any]] = {}
CACHE_TTL = 5.0  # seconds


def _get_lock(name: str) -> threading.Lock:
    """Get or create a lock for a state file."""
    with _lock_lock:
        if name not in _locks:
            _locks[name] = threading.Lock()
        return _locks[name]


def _atomic_write(path: Path, data: dict) -> bool:
    """Write data atomically using temp file + rename."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)

        # Write to temp file in same directory (for atomic rename)
        fd, temp_path = tempfile.mkstemp(
            dir=path.parent,
            prefix=f".{path.stem}_",
            suffix=".tmp"
        )
        try:
            with os.fdopen(fd, 'w') as f:
                json.dump(data, f, indent=2, default=str)

            # Atomic rename
            os.replace(temp_path, path)
            return True
        except Exception:
            # Clean up temp file on error
            try:
                os.unlink(temp_path)
            except Exception:
                pass
            raise
    except Exception:
        return False


def _read_json(path: Path, default: dict | None = None) -> dict:
    """Read JSON file with error handling."""
    if default is None:
        default = {}

    if not path.exists():
        return default.copy()

    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return default.copy()


class StateManager:
    """Unified state manager for all hook state."""

    def __init__(self):
        self.data_dir = DATA_DIR
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def _get_path(self, name: str) -> Path:
        """Get path for a state file."""
        return self.data_dir / f"{name}.json"

    def read(self, name: str, default: dict | None = None) -> dict:
        """Read state with caching."""
        cache_key = name
        now = datetime.now().timestamp()

        # Check cache
        if cache_key in _cache:
            cached_time, cached_data = _cache[cache_key]
            if now - cached_time < CACHE_TTL:
                return cached_data.copy()

        # Read from file
        path = self._get_path(name)
        data = _read_json(path, default or {})

        # Update cache
        _cache[cache_key] = (now, data.copy())

        return data

    def write(self, name: str, data: dict) -> bool:
        """Write state atomically with locking."""
        lock = _get_lock(name)
        path = self._get_path(name)

        with lock:
            success = _atomic_write(path, data)
            if success:
                # Update cache
                _cache[name] = (datetime.now().timestamp(), data.copy())
            return success

    def update(self, name: str, updater: Callable[[dict], dict], default: dict | None = None) -> bool:
        """Read-modify-write with locking."""
        lock = _get_lock(name)

        with lock:
            data = self.read(name, default)
            updated = updater(data)
            return self.write(name, updated)

    def invalidate_cache(self, name: str | None = None):
        """Invalidate cache for a state file or all files."""
        if name:
            _cache.pop(name, None)
        else:
            _cache.clear()

    # ========== Specialized Accessors ==========

    # --- Checkpoint State ---
    def get_checkpoints(self) -> dict:
        """Get checkpoint state."""
        return self.read("checkpoint-state", {
            "last_checkpoint": 0,
            "checkpoints": []
        })

    def add_checkpoint(self, session_id: str, file_path: str, reason: str, cwd: str = "") -> dict:
        """Add a checkpoint entry."""
        now = datetime.now()
        checkpoint = {
            "timestamp": now.isoformat(),
            "session_id": session_id,
            "file": file_path,
            "reason": reason,
            "cwd": cwd,
        }

        def updater(state):
            state.setdefault("checkpoints", []).append(checkpoint)
            state["checkpoints"] = state["checkpoints"][-20:]  # Keep last 20
            state["last_checkpoint"] = now.timestamp()
            return state

        self.update("checkpoint-state", updater)
        return checkpoint

    # --- Usage Stats ---
    def get_usage_stats(self) -> dict:
        """Get usage statistics."""
        return self.read("usage-stats", {
            "agents": {},
            "skills": {},
            "commands": {},
            "daily": {}
        })

    def record_usage(self, category: str, name: str):
        """Record usage of an agent, skill, or command."""
        today = datetime.now().strftime("%Y-%m-%d")

        def updater(stats):
            # Update lifetime count
            stats.setdefault(category, {})
            stats[category].setdefault(name, {"count": 0, "last_used": ""})
            stats[category][name]["count"] += 1
            stats[category][name]["last_used"] = datetime.now().isoformat()

            # Update daily count
            stats.setdefault("daily", {})
            stats["daily"].setdefault(today, {"agents": 0, "skills": 0, "commands": 0})
            if category in stats["daily"][today]:
                stats["daily"][today][category] += 1

            return stats

        self.update("usage-stats", updater)

    # --- Permission Patterns ---
    def get_permission_patterns(self) -> dict:
        """Get learned permission patterns."""
        return self.read("permission-patterns", {"patterns": {}, "updated": None})

    def record_permission(self, pattern_key: str) -> int:
        """Record a permission approval, return new count."""
        now = datetime.now()
        count = 0

        def updater(data):
            nonlocal count
            data.setdefault("patterns", {})
            if pattern_key not in data["patterns"]:
                data["patterns"][pattern_key] = {
                    "count": 0,
                    "first_seen": now.isoformat()
                }
            data["patterns"][pattern_key]["count"] += 1
            data["patterns"][pattern_key]["last_seen"] = now.isoformat()
            data["updated"] = now.isoformat()
            count = data["patterns"][pattern_key]["count"]
            return data

        self.update("permission-patterns", updater)
        return count

    def get_permission_count(self, pattern_key: str) -> int:
        """Get count for a permission pattern."""
        data = self.get_permission_patterns()
        return data.get("patterns", {}).get(pattern_key, {}).get("count", 0)

    # --- Session History ---
    def get_session_history(self) -> dict:
        """Get session history."""
        return self.read("session-history", {"sessions": [], "updated": None})

    def add_session(self, session_id: str, metadata: dict):
        """Add or update a session entry."""
        now = datetime.now()

        def updater(data):
            data.setdefault("sessions", [])

            # Check if session exists
            for session in data["sessions"]:
                if session.get("id") == session_id:
                    session.update(metadata)
                    session["updated"] = now.isoformat()
                    data["updated"] = now.isoformat()
                    return data

            # Add new session
            entry = {"id": session_id, "created": now.isoformat(), **metadata}
            data["sessions"].append(entry)
            data["sessions"] = data["sessions"][-100:]  # Keep last 100
            data["updated"] = now.isoformat()
            return data

        self.update("session-history", updater)

    # --- Token Usage ---
    def get_token_usage(self) -> dict:
        """Get token usage data."""
        return self.read("token-usage", {"daily": {}, "updated": None})

    def record_tokens(self, input_tokens: int = 0, output_tokens: int = 0):
        """Record token usage for today."""
        today = datetime.now().strftime("%Y-%m-%d")

        def updater(data):
            data.setdefault("daily", {})
            data["daily"].setdefault(today, {"input": 0, "output": 0})
            data["daily"][today]["input"] += input_tokens
            data["daily"][today]["output"] += output_tokens
            data["updated"] = datetime.now().isoformat()
            return data

        self.update("token-usage", updater)

    # --- Exploration Cache ---
    def get_exploration_cache(self) -> dict:
        """Get exploration cache."""
        return self.read("exploration-cache", {"entries": {}, "updated": None})

    def cache_exploration(self, key: str, result: str, ttl_hours: int = 24):
        """Cache an exploration result."""
        now = datetime.now()
        expires = now.timestamp() + (ttl_hours * 3600)

        def updater(data):
            data.setdefault("entries", {})
            data["entries"][key] = {
                "result": result[:5000],  # Limit size
                "cached": now.isoformat(),
                "expires": expires
            }
            # Clean expired entries
            current = now.timestamp()
            data["entries"] = {
                k: v for k, v in data["entries"].items()
                if v.get("expires", 0) > current
            }
            data["updated"] = now.isoformat()
            return data

        self.update("exploration-cache", updater)

    def get_cached_exploration(self, key: str) -> str | None:
        """Get cached exploration if not expired."""
        data = self.get_exploration_cache()
        entry = data.get("entries", {}).get(key)

        if entry and entry.get("expires", 0) > datetime.now().timestamp():
            return entry.get("result")
        return None

    # --- Research Cache ---
    def get_research_cache(self) -> dict:
        """Get research cache."""
        return self.read("research-cache", {"entries": {}, "updated": None})

    def cache_research(self, key: str, result: str, ttl_hours: int = 48):
        """Cache a research result."""
        now = datetime.now()
        expires = now.timestamp() + (ttl_hours * 3600)

        def updater(data):
            data.setdefault("entries", {})
            data["entries"][key] = {
                "result": result[:10000],  # Limit size
                "cached": now.isoformat(),
                "expires": expires
            }
            # Clean expired entries
            current = now.timestamp()
            data["entries"] = {
                k: v for k, v in data["entries"].items()
                if v.get("expires", 0) > current
            }
            data["updated"] = now.isoformat()
            return data

        self.update("research-cache", updater)

    def get_cached_research(self, key: str) -> str | None:
        """Get cached research if not expired."""
        data = self.get_research_cache()
        entry = data.get("entries", {}).get(key)

        if entry and entry.get("expires", 0) > datetime.now().timestamp():
            return entry.get("result")
        return None


# Global singleton instance
_manager: StateManager | None = None


def get_state_manager() -> StateManager:
    """Get the global state manager instance."""
    global _manager
    if _manager is None:
        _manager = StateManager()
    return _manager


# Convenience functions
def read_state(name: str, default: dict | None = None) -> dict:
    """Read state file."""
    return get_state_manager().read(name, default)


def write_state(name: str, data: dict) -> bool:
    """Write state file atomically."""
    return get_state_manager().write(name, data)


def update_state(name: str, updater: Callable[[dict], dict], default: dict | None = None) -> bool:
    """Update state with read-modify-write."""
    return get_state_manager().update(name, updater, default)

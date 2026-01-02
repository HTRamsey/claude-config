"""
Hook configuration and utilities.

Uses cache abstraction for automatic expiration.
"""
import os
from datetime import datetime

from .cache import create_ttl_cache
from .io import safe_load_json
from .state import read_state, update_state
from .session import get_session_id
from .logging import DATA_DIR

# Import centralized config
try:
    from config import Timeouts
    HOOK_DISABLED_TTL = Timeouts.HOOK_DISABLED_TTL
except ImportError:
    HOOK_DISABLED_TTL = 10.0  # Fallback

# TTL cache for hook disabled status (no lock needed - single-threaded access pattern)
_hook_disabled_cache = create_ttl_cache(maxsize=50, ttl=HOOK_DISABLED_TTL)


def is_hook_disabled(name: str) -> bool:
    """
    Check if hook is disabled globally or for current session.

    Priority:
        1. Session override (takes precedence)
        2. Global disabled list

    Note: Results are cached for 10 seconds to avoid repeated file I/O.
    """
    if name in _hook_disabled_cache:
        return _hook_disabled_cache[name]

    result = _check_hook_disabled_uncached(name)
    _hook_disabled_cache[name] = result
    return result


def _check_hook_disabled_uncached(name: str) -> bool:
    """Uncached implementation of is_hook_disabled."""
    session_hooks_dir = DATA_DIR / "session-hooks"
    session_id = get_session_id()  # Use centralized session ID retrieval

    if session_id and session_id != "default":
        session_override_file = session_hooks_dir / f"{session_id}.json"
        if session_override_file.exists():
            try:
                session_data = safe_load_json(session_override_file)
                override = session_data.get("overrides", {}).get(name)
                if override is False:
                    return True
                elif override is True:
                    return False
            except Exception:
                pass

    config_file = DATA_DIR / "hook-config.json"
    if config_file.exists():
        config = safe_load_json(config_file)
        if name in config.get("disabled", []):
            return True

    return False


def record_usage(category: str, name: str):
    """
    Record usage of an agent, skill, or command.

    Args:
        category: "agents", "skills", or "commands"
        name: Name of the item
    """
    today = datetime.now().strftime("%Y-%m-%d")

    def updater(stats):
        stats.setdefault(category, {})
        stats[category].setdefault(name, {"count": 0, "last_used": ""})
        stats[category][name]["count"] += 1
        stats[category][name]["last_used"] = datetime.now().isoformat()

        stats.setdefault("daily", {})
        stats["daily"].setdefault(today, {"agents": 0, "skills": 0, "commands": 0})
        if category in stats["daily"][today]:
            stats["daily"][today][category] += 1

        stats["last_updated"] = datetime.now().isoformat()
        return stats

    update_state("usage-stats", updater, {
        "agents": {}, "skills": {}, "commands": {}, "daily": {}
    })




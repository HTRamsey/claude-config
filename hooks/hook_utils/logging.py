"""
Logging and graceful degradation utilities.
"""
import json
import os
import sys
from functools import wraps
from pathlib import Path
from typing import Callable

from .io import file_lock
from .metrics import get_timestamp
from hooks.config import fast_json_loads, fast_json_dumps

DATA_DIR = Path(os.environ.get("CLAUDE_DATA_DIR", Path.home() / ".claude" / "data"))
LOG_FILE = DATA_DIR / "hook-events.jsonl"


def ensure_data_dir():
    """Ensure data directory exists."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def log_event(hook_name: str, event_type: str, data: dict = None, level: str = "info"):
    """
    Append structured JSON log entry with file locking.

    Uses msgspec for fast serialization.
    Never raises - always succeeds silently.
    """
    try:
        ensure_data_dir()
        entry = {
            "timestamp": get_timestamp(),
            "hook": hook_name,
            "event": event_type,
            "level": level,
            "data": data or {}
        }
        with open(LOG_FILE, 'ab') as f:
            with file_lock(f):
                f.write(fast_json_dumps(entry) + b"\n")
    except Exception:
        pass


def graceful_main(hook_name: str, check_disabled: bool = True):
    """
    Decorator for hook main functions.
    Ensures graceful degradation - logs errors but never blocks.

    Args:
        hook_name: Name of the hook for logging and disable checks
        check_disabled: If True, check is_hook_disabled before running (default: True)

    Usage:
        @graceful_main("my_hook")
        def main():
            # hook logic here
            pass
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                # Check if hook is disabled (lazy import to avoid circular deps)
                if check_disabled:
                    from .hooks import is_hook_disabled
                    if is_hook_disabled(hook_name):
                        sys.exit(0)
                return func(*args, **kwargs)
            except json.JSONDecodeError as e:
                log_event(hook_name, "error", {"type": "json_decode", "msg": str(e)}, "error")
                sys.exit(0)
            except Exception as e:
                log_event(hook_name, "error", {"type": type(e).__name__, "msg": str(e)}, "error")
                sys.exit(0)
        return wrapper
    return decorator


def read_stdin_context() -> dict:
    """Read and parse stdin context using msgspec."""
    try:
        data = sys.stdin.buffer.read()
        return fast_json_loads(data) if data else {}
    except Exception:
        return {}



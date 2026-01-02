"""
Logging and graceful degradation utilities.

Uses loguru for structured JSON logging with automatic rotation.
Includes log-once pattern for suppressing duplicate errors.
"""
import json
import os
import sys
import time
from functools import wraps
from pathlib import Path
from typing import Callable

from loguru import logger

from hooks.config import fast_json_loads


# =============================================================================
# Log-Once Pattern - Suppress duplicate errors within a time window
# =============================================================================

class LogOnce:
    """Rate-limited logging that suppresses duplicates within a time window.

    Usage:
        _log_once = LogOnce(period_sec=300)

        try:
            ...
        except Exception as e:
            _log_once.error("my_handler", "database_error", str(e))
    """

    def __init__(self, period_sec: int = 300):
        self.period_sec = period_sec
        self._cache: dict[tuple, tuple[float, int]] = {}  # key -> (first_seen, count)

    def _should_log(self, key: tuple) -> tuple[bool, int]:
        """Check if this message should be logged.

        Returns:
            (should_log, suppressed_count) - whether to log and how many were suppressed
        """
        now = time.time()

        if key in self._cache:
            first_seen, count = self._cache[key]
            if now - first_seen < self.period_sec:
                self._cache[key] = (first_seen, count + 1)
                return False, 0
            # Window expired - log with suppression count
            suppressed = count - 1  # Don't count the first one
            self._cache[key] = (now, 1)
            return True, suppressed

        self._cache[key] = (now, 1)
        return True, 0

    def error(self, hook_name: str, event_type: str, message: str, **extra):
        """Log an error, suppressing duplicates within the time window."""
        key = (hook_name, event_type, message)
        should_log, suppressed = self._should_log(key)

        if should_log:
            data = {"msg": message, **extra}
            if suppressed > 0:
                data["suppressed"] = suppressed
            log_event(hook_name, event_type, data, "error")

    def warning(self, hook_name: str, event_type: str, message: str, **extra):
        """Log a warning, suppressing duplicates within the time window."""
        key = (hook_name, event_type, message)
        should_log, suppressed = self._should_log(key)

        if should_log:
            data = {"msg": message, **extra}
            if suppressed > 0:
                data["suppressed"] = suppressed
            log_event(hook_name, event_type, data, "warning")


# Global log-once instance (5 minute window)
_log_once = LogOnce(period_sec=300)

DATA_DIR = Path(os.environ.get("CLAUDE_DATA_DIR", Path.home() / ".claude" / "data"))
LOG_FILE = DATA_DIR / "hook-events.jsonl"

# Configure loguru: JSON format, 10MB rotation, keep 3 files
# Remove default stderr handler, add file handler
logger.remove()
DATA_DIR.mkdir(parents=True, exist_ok=True)
logger.add(
    LOG_FILE,
    format="{message}",
    serialize=True,  # JSON output
    rotation="10 MB",
    retention=3,
    compression="gz",
    enqueue=True,  # Thread-safe
    catch=True,  # Never raise
)


def log_event(hook_name: str, event_type: str, data: dict = None, level: str = "info"):
    """
    Log structured event using loguru.

    Args:
        hook_name: Name of the hook (e.g., "file_protection")
        event_type: Event type (e.g., "blocked", "error")
        data: Additional context data
        level: Log level (debug, info, warning, error)
    """
    try:
        log_func = getattr(logger, level, logger.info)
        log_func(event_type, hook=hook_name, **(data or {}))
    except Exception:
        pass  # Never raise


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



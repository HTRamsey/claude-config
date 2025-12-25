#!/home/jonglaser/.claude/venv/bin/python3
"""
Shared utilities for Claude Code hooks.
Provides unified logging, graceful degradation, and common patterns.
"""
import json
import os
import sys
import hashlib
from datetime import datetime
from pathlib import Path
from functools import wraps

# Paths
DATA_DIR = Path(os.environ.get("CLAUDE_DATA_DIR", Path.home() / ".claude" / "data"))
LOG_FILE = DATA_DIR / "hook-events.jsonl"
SESSION_STATE_FILE = DATA_DIR / "session-state.json"

def ensure_data_dir():
    """Ensure data directory exists."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

def log_event(hook_name: str, event_type: str, data: dict = None, level: str = "info"):
    """
    Append structured JSON log entry.

    Args:
        hook_name: Name of the hook
        event_type: Type of event (start, success, error, warning)
        data: Additional data to log
        level: Log level (debug, info, warning, error)
    """
    try:
        ensure_data_dir()
        entry = {
            "timestamp": datetime.now().isoformat(),
            "hook": hook_name,
            "event": event_type,
            "level": level,
            "data": data or {}
        }
        with open(LOG_FILE, 'a') as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass  # Never fail on logging

def graceful_main(hook_name: str):
    """
    Decorator for hook main functions.
    Ensures graceful degradation - logs errors but never blocks.

    Usage:
        @graceful_main("my_hook")
        def main():
            # hook logic here
            pass
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except json.JSONDecodeError as e:
                log_event(hook_name, "error", {"type": "json_decode", "msg": str(e)}, "error")
                sys.exit(0)  # Don't block on bad input
            except Exception as e:
                log_event(hook_name, "error", {"type": type(e).__name__, "msg": str(e)}, "error")
                sys.exit(0)  # Never block on errors
        return wrapper
    return decorator

def get_session_id(ctx: dict = None, transcript_path: str = None) -> str:
    """
    Get consistent session ID from context or generate one.

    Args:
        ctx: Context dict (may contain session_id)
        transcript_path: Transcript path to hash (fallback)

    Returns:
        Session ID string (never empty, defaults to "default")

    Priority:
        1. ctx["session_id"] if available
        2. CLAUDE_SESSION_ID environment variable
        3. Hash of transcript_path if provided
        4. "default" as final fallback
    """
    import time

    # Priority 1: Context session_id
    if ctx and ctx.get("session_id"):
        return ctx["session_id"]

    # Priority 2: Environment variable
    session_from_env = os.environ.get("CLAUDE_SESSION_ID")
    if session_from_env:
        return session_from_env

    # Priority 3: Hash transcript_path
    # Support both direct argument and ctx["transcript_path"]
    path = transcript_path or (ctx.get("transcript_path") if ctx else None)
    if path:
        return hashlib.md5(path.encode()).hexdigest()[:8]

    # Priority 4: Default fallback
    return "default"

def is_new_session(ctx: dict = None, transcript_path: str = None) -> bool:
    """
    Check if this is a new session (first message).
    Uses session state file to track seen sessions.

    Args:
        ctx: Context dict (preferred)
        transcript_path: Transcript path (fallback)
    """
    try:
        ensure_data_dir()
        session_id = get_session_id(ctx, transcript_path)

        state = {}
        if SESSION_STATE_FILE.exists():
            with open(SESSION_STATE_FILE) as f:
                state = json.load(f)

        seen_sessions = state.get("seen_sessions", [])

        if session_id not in seen_sessions:
            # New session - mark as seen
            seen_sessions.append(session_id)
            # Keep only last 100 sessions
            state["seen_sessions"] = seen_sessions[-100:]
            state["last_session"] = session_id
            state["last_session_start"] = datetime.now().isoformat()

            with open(SESSION_STATE_FILE, 'w') as f:
                json.dump(state, f, indent=2)

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

def update_session_state(updates: dict):
    """Update session state with new values."""
    try:
        ensure_data_dir()
        state = get_session_state()
        state.update(updates)
        with open(SESSION_STATE_FILE, 'w') as f:
            json.dump(state, f, indent=2)
    except Exception:
        pass

def backup_transcript(transcript_path: str, reason: str = "manual", ctx: dict = None) -> str:
    """
    Backup transcript to data directory.

    Args:
        transcript_path: Path to transcript file
        reason: Reason for backup (pre_compact, checkpoint, etc.)
        ctx: Context dict (optional, for session ID)

    Returns:
        Path to backup file, or empty string on failure
    """
    try:
        if not transcript_path or not os.path.exists(transcript_path):
            return ""

        ensure_data_dir()
        backup_dir = DATA_DIR / "transcript-backups"
        backup_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        session_id = get_session_id(ctx, transcript_path)
        backup_name = f"{session_id}-{reason}-{timestamp}.jsonl"
        backup_path = backup_dir / backup_name

        # Copy file
        with open(transcript_path, 'rb') as src:
            with open(backup_path, 'wb') as dst:
                dst.write(src.read())

        log_event("backup", "success", {
            "reason": reason,
            "path": str(backup_path),
            "size": os.path.getsize(backup_path)
        })

        # Clean old backups (keep last 20)
        backups = sorted(backup_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime)
        for old_backup in backups[:-20]:
            old_backup.unlink()

        return str(backup_path)
    except Exception as e:
        log_event("backup", "error", {"reason": reason, "error": str(e)}, "error")
        return ""

def read_stdin_context() -> dict:
    """Read and parse stdin context, with graceful fallback."""
    try:
        return json.load(sys.stdin)
    except (json.JSONDecodeError, Exception):
        return {}

def output_message(message: str, to_stderr: bool = False):
    """Output message to appropriate stream."""
    stream = sys.stderr if to_stderr else sys.stdout
    print(message, file=stream)


def safe_load_json(path: Path, default: dict = None) -> dict:
    """
    Load JSON file with graceful fallback.

    Args:
        path: Path to JSON file
        default: Default value if file doesn't exist or is invalid

    Returns:
        Parsed JSON dict, or default on any error
    """
    if default is None:
        default = {}
    try:
        if path.exists():
            with open(path) as f:
                return json.load(f)
    except (json.JSONDecodeError, IOError, OSError):
        pass
    return default.copy() if isinstance(default, dict) else default


def safe_save_json(path: Path, data: dict, indent: int = 2) -> bool:
    """
    Save JSON file with graceful error handling.

    Args:
        path: Path to save to
        data: Dict to save
        indent: JSON indent level

    Returns:
        True on success, False on any error
    """
    try:
        ensure_data_dir()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w') as f:
            json.dump(data, f, indent=indent)
        return True
    except (IOError, OSError, TypeError):
        return False


def safe_append_jsonl(path: Path, entry: dict) -> bool:
    """
    Append entry to JSONL file with graceful error handling.

    Args:
        path: Path to JSONL file
        entry: Dict to append as JSON line

    Returns:
        True on success, False on any error
    """
    try:
        ensure_data_dir()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'a') as f:
            f.write(json.dumps(entry) + "\n")
        return True
    except (IOError, OSError, TypeError):
        return False

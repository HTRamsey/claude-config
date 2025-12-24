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

def get_session_id(transcript_path: str) -> str:
    """Get or generate a session ID from transcript path."""
    if not transcript_path:
        return "unknown"
    return hashlib.md5(transcript_path.encode()).hexdigest()[:8]

def is_new_session(transcript_path: str) -> bool:
    """
    Check if this is a new session (first message).
    Uses session state file to track seen sessions.
    """
    try:
        ensure_data_dir()
        session_id = get_session_id(transcript_path)

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

def backup_transcript(transcript_path: str, reason: str = "manual") -> str:
    """
    Backup transcript to data directory.

    Args:
        transcript_path: Path to transcript file
        reason: Reason for backup (pre_compact, checkpoint, etc.)

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
        session_id = get_session_id(transcript_path)
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

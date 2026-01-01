#!/home/jonglaser/.claude/data/venv/bin/python3
"""
Checkpoint management - backup and checkpoint logic for context preservation.

Provides:
- Checkpoint state management (tracking risky operations)
- Error backup management (saving failed command context)
- Risk detection for edit operations
"""
import time
from pathlib import Path
from datetime import datetime

from hooks.config import Timeouts, Thresholds, StateSaver, DATA_DIR
from hooks.hook_utils import (
    log_event,
    read_state,
    write_state,
    safe_save_json,
)
from hooks.hook_sdk import PreToolUseContext

# Configuration
STATE_KEY = "checkpoint"
ERROR_BACKUP_DIR = DATA_DIR / "error-backups"
CHECKPOINT_INTERVAL = Timeouts.CHECKPOINT_INTERVAL
MAX_ERROR_BACKUPS = Thresholds.MAX_ERROR_BACKUPS


# ==============================================================================
# Checkpoint State Management
# ==============================================================================

def load_state() -> dict:
    """Load checkpoint state using unified state API."""
    return read_state(STATE_KEY, {"last_checkpoint": 0, "checkpoints": []})


def save_state(state: dict):
    """Save checkpoint state using unified state API."""
    write_state(STATE_KEY, state)


def is_risky_operation(file_path: str, content: str = "") -> tuple[bool, str]:
    """Determine if operation is risky and needs checkpoint."""
    path_str = str(file_path).lower()

    # Get compiled risky patterns from config
    risky_patterns = StateSaver.get_patterns()
    for pattern in risky_patterns:
        if pattern.search(path_str):
            return True, "risky pattern detected"

    content_lower = content.lower()
    for keyword in StateSaver.RISKY_KEYWORDS:
        if keyword in content_lower:
            return True, f"contains '{keyword}' operation"

    if len(content) > 500:
        return True, "large edit (>500 chars)"

    return False, ""


def should_checkpoint(state: dict) -> bool:
    """Check if we should create a new checkpoint."""
    last = state.get("last_checkpoint", 0)
    return (time.time() - last) > CHECKPOINT_INTERVAL


def save_checkpoint_entry(session_id: str, file_path: str, reason: str, ctx: PreToolUseContext) -> dict:
    """Save checkpoint info to state file."""
    state = load_state()
    now = datetime.now()

    checkpoint = {
        "timestamp": now.isoformat(),
        "session_id": session_id,
        "file": file_path,
        "reason": reason,
        "cwd": ctx.cwd,
    }

    state["checkpoints"].append(checkpoint)
    state["checkpoints"] = state["checkpoints"][-20:]  # Keep last 20
    state["last_checkpoint"] = now.timestamp()
    save_state(state)

    return checkpoint


# ==============================================================================
# Error Backup Management
# ==============================================================================

def rotate_error_backups():
    """Keep only the most recent error backups."""
    if not ERROR_BACKUP_DIR.exists():
        return

    backups = sorted(ERROR_BACKUP_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime)
    while len(backups) > MAX_ERROR_BACKUPS:
        oldest = backups.pop(0)
        try:
            oldest.unlink()
        except Exception:
            pass


def save_error_backup(raw: dict, command: str, exit_code: int, output: str) -> str | None:
    """Save error context to backup file."""
    try:
        ERROR_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        now = datetime.now()
        filename = f"error_{now.strftime('%Y%m%d_%H%M%S')}.json"
        backup_path = ERROR_BACKUP_DIR / filename

        # Truncate output if too large
        if len(output) > 10000:
            output = output[:5000] + "\n...[truncated]...\n" + output[-2000:]

        backup_data = {
            "timestamp": now.isoformat(),
            "session_id": raw.get("session_id", "unknown"),
            "cwd": raw.get("cwd", ""),
            "command": command[:500],  # Truncate long commands
            "exit_code": exit_code,
            "output": output,
        }

        if safe_save_json(backup_path, backup_data, indent=2):
            rotate_error_backups()
            return str(backup_path)
        return None

    except Exception as e:
        log_event("checkpoint", "error_backup_failed", {"error": str(e)})
        return None

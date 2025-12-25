#!/home/jonglaser/.claude/venv/bin/python3
"""
State Saver Hook - Saves context before risky operations and compaction.

Consolidates context_checkpoint.py and precompact_save.py.

Runs on:
- PreToolUse (Edit, Write): Save checkpoint before risky edits
- PreCompact: Backup transcript before compaction
"""
import json
import re
import sys
import time
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))
from hook_utils import (
    graceful_main,
    log_event,
    backup_transcript,
    update_session_state,
    get_session_id,
)

# Configuration
STATE_FILE = Path.home() / ".claude/data/checkpoint-state.json"
ERROR_BACKUP_DIR = Path.home() / ".claude/data/error-backups"
CHECKPOINT_INTERVAL = 300  # Min seconds between checkpoints
MAX_ERROR_BACKUPS = 20  # Keep last N error backups

RISKY_PATTERNS = [
    r'(config|settings|env)\.(json|yaml|yml|toml)$',
    r'package\.json$',
    r'Cargo\.toml$',
    r'pyproject\.toml$',
    r'docker-compose',
    r'Dockerfile',
    r'\.github/workflows/',
    r'migrations/',
    r'schema\.',
]
RISKY_KEYWORDS = ['delete', 'remove', 'drop', 'truncate', 'reset', 'destroy']


def load_state() -> dict:
    """Load checkpoint state."""
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {"last_checkpoint": 0, "checkpoints": []}


def save_state(state: dict):
    """Save checkpoint state."""
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(STATE_FILE, "w") as f:
            json.dump(state, f)
    except Exception:
        pass


def is_risky_operation(file_path: str, content: str = "") -> tuple[bool, str]:
    """Determine if operation is risky and needs checkpoint."""
    path_str = str(file_path).lower()

    for pattern in RISKY_PATTERNS:
        if re.search(pattern, path_str, re.IGNORECASE):
            return True, f"config/critical file: {pattern}"

    content_lower = content.lower()
    for keyword in RISKY_KEYWORDS:
        if keyword in content_lower:
            return True, f"contains '{keyword}' operation"

    if len(content) > 500:
        return True, "large edit (>500 chars)"

    return False, ""


def should_checkpoint(state: dict) -> bool:
    """Check if we should create a new checkpoint."""
    last = state.get("last_checkpoint", 0)
    return (time.time() - last) > CHECKPOINT_INTERVAL


def save_checkpoint_entry(session_id: str, file_path: str, reason: str, ctx: dict) -> dict:
    """Save checkpoint info to state file."""
    state = load_state()
    now = datetime.now()

    checkpoint = {
        "timestamp": now.isoformat(),
        "session_id": session_id,
        "file": file_path,
        "reason": reason,
        "cwd": ctx.get("cwd", ""),
    }

    state["checkpoints"].append(checkpoint)
    state["checkpoints"] = state["checkpoints"][-20:]  # Keep last 20
    state["last_checkpoint"] = now.timestamp()
    save_state(state)

    return checkpoint


def handle_pre_tool_use(ctx: dict) -> dict | None:
    """Save checkpoint before risky edit operations."""
    tool_name = ctx.get("tool_name", "")
    tool_input = ctx.get("tool_input", {})
    session_id = get_session_id(ctx)

    if tool_name not in ("Edit", "Write"):
        return None

    file_path = tool_input.get("file_path", "")
    content = tool_input.get("content", "") or tool_input.get("new_string", "")

    if not file_path:
        return None

    state = load_state()
    risky, reason = is_risky_operation(file_path, content)

    if risky and should_checkpoint(state):
        save_checkpoint_entry(session_id, file_path, reason, ctx)
        filename = Path(file_path).name
        log_event("state_saver", "checkpoint", {"file": filename, "reason": reason})
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "permissionDecisionReason": f"[Checkpoint] {filename} ({reason})"
            }
        }

    return None


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


def save_error_backup(ctx: dict, command: str, exit_code: int, output: str) -> str | None:
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
            "session_id": ctx.get("session_id", "unknown"),
            "cwd": ctx.get("cwd", ""),
            "command": command[:500],  # Truncate long commands
            "exit_code": exit_code,
            "output": output,
        }

        with open(backup_path, "w") as f:
            json.dump(backup_data, f, indent=2)

        rotate_error_backups()
        return str(backup_path)

    except Exception as e:
        log_event("state_saver", "error_backup_failed", {"error": str(e)})
        return None


def handle_post_tool_use(ctx: dict) -> dict | None:
    """Save error backup when commands fail."""
    tool_name = ctx.get("tool_name", "")

    if tool_name != "Bash":
        return None

    tool_input = ctx.get("tool_input", {})
    tool_result = ctx.get("tool_result", {})

    command = tool_input.get("command", "")

    # Get exit code from various possible locations
    exit_code = tool_result.get("exit_code")
    if exit_code is None:
        exit_code = tool_result.get("exitCode")
    if exit_code is None:
        return None

    # Only backup on errors
    if exit_code == 0:
        return None

    # Get output
    stdout = str(tool_result.get("stdout", ""))
    stderr = str(tool_result.get("stderr", ""))
    output = stdout + "\n" + stderr if stderr else stdout

    # Save backup
    backup_path = save_error_backup(ctx, command, exit_code, output)

    if backup_path:
        log_event("state_saver", "error_backup", {
            "command": command[:100],
            "exit_code": exit_code,
            "backup": backup_path
        })

    return None


def handle_pre_compact(ctx: dict) -> dict | None:
    """Backup transcript before compaction."""
    transcript_path = ctx.get("transcript_path", "")

    if not transcript_path:
        return None

    backup_path = backup_transcript(transcript_path, reason="pre_compact")

    if backup_path:
        update_session_state({
            "last_compact_backup": backup_path,
            "last_compact_time": datetime.now().isoformat()
        })
        log_event("state_saver", "pre_compact_backup", {"backup_path": backup_path})

    return None


@graceful_main("state_saver")
def main():
    try:
        ctx = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = ctx.get("tool_name", "")

    # Detect event type
    if "transcript_path" in ctx and tool_name == "":
        # PreCompact event
        handle_pre_compact(ctx)
    elif tool_name in ("Edit", "Write"):
        # PreToolUse event
        result = handle_pre_tool_use(ctx)
        if result:
            print(json.dumps(result))

    sys.exit(0)


if __name__ == "__main__":
    main()

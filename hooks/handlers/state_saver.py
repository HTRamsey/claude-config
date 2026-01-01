#!/home/jonglaser/.claude/data/venv/bin/python3
"""
State Saver Hook - Saves context before risky operations and compaction.

Consolidates context_checkpoint.py and precompact_save.py.

Runs on:
- PreToolUse (Edit, Write): Save checkpoint before risky edits
- PreCompact: Backup transcript before compaction
"""
import json
import sys
import time
from pathlib import Path
from datetime import datetime

from hooks.config import Timeouts, Thresholds, StateSaver, DATA_DIR
from hooks.hook_utils import (
    graceful_main,
    log_event,
    backup_transcript,
    update_session_state,
    get_session_id,
    read_state,
    write_state,
    safe_save_json,
)
from hooks.hook_sdk import PreToolUseContext, PostToolUseContext, Response

# Configuration
STATE_KEY = "checkpoint"
ERROR_BACKUP_DIR = DATA_DIR / "error-backups"
CHECKPOINT_INTERVAL = Timeouts.CHECKPOINT_INTERVAL
MAX_ERROR_BACKUPS = Thresholds.MAX_ERROR_BACKUPS


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
            return True, f"risky pattern detected"

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


def handle_pre_tool_use(raw: dict) -> dict | None:
    """Save checkpoint before risky edit operations."""
    ctx = PreToolUseContext(raw)
    session_id = get_session_id(raw)

    if ctx.tool_name not in ("Edit", "Write"):
        return None

    file_path = ctx.tool_input.file_path
    content = ctx.tool_input.content or ctx.tool_input.new_string

    if not file_path:
        return None

    state = load_state()
    risky, reason = is_risky_operation(file_path, content)

    if risky and should_checkpoint(state):
        save_checkpoint_entry(session_id, file_path, reason, ctx)
        filename = Path(file_path).name
        log_event("state_saver", "checkpoint", {"file": filename, "reason": reason})
        return Response.allow(f"[Checkpoint] {filename} ({reason})")

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

        if safe_save_json(backup_path, backup_data, indent=2):
            rotate_error_backups()
            return str(backup_path)
        return None

    except Exception as e:
        log_event("state_saver", "error_backup_failed", {"error": str(e)})
        return None


def handle_post_tool_use(raw: dict) -> dict | None:
    """Save error backup when commands fail."""
    ctx = PostToolUseContext(raw)

    if ctx.tool_name != "Bash":
        return None

    command = ctx.tool_input.command

    # Get exit code
    exit_code = ctx.tool_result.exit_code
    if exit_code is None:
        return None

    # Only backup on errors
    if exit_code == 0:
        return None

    # Get output
    output = ctx.tool_result.output

    # Save backup
    backup_path = save_error_backup(raw, command, exit_code, output)

    if backup_path:
        log_event("state_saver", "error_backup", {
            "command": command[:100],
            "exit_code": exit_code,
            "backup": backup_path
        })

    return None


def get_claude_md_content(cwd: str) -> str:
    """Extract key content from CLAUDE.md files for preservation."""
    claude_md_paths = [
        Path(cwd) / "CLAUDE.md",
        Path(cwd) / ".claude" / "CLAUDE.md",
    ]

    for path in claude_md_paths:
        if path.exists():
            try:
                content = path.read_text()[:2000]  # First 2000 chars
                return f"[Project CLAUDE.md preserved]\n{content}"
            except Exception:
                pass
    return ""


def get_active_todos(ctx: dict) -> str:
    """Extract active todos from context if present."""
    # Check if there's a todos key in context (from TodoWrite tool state)
    todos = ctx.get("todos", [])
    if not todos:
        return ""

    active = [t for t in todos if t.get("status") in ("pending", "in_progress")]
    if not active:
        return ""

    lines = ["[Active Todos preserved]"]
    for t in active[:10]:  # Max 10 todos
        status = "→" if t.get("status") == "in_progress" else "○"
        lines.append(f"  {status} {t.get('content', '')}")

    return "\n".join(lines)


def get_key_context(ctx: dict) -> str:
    """Extract key context that should survive compaction."""
    parts = []
    cwd = ctx.get("cwd", "")

    # CLAUDE.md content
    claude_md = get_claude_md_content(cwd)
    if claude_md:
        parts.append(claude_md)

    # Active todos
    todos = get_active_todos(ctx)
    if todos:
        parts.append(todos)

    # Current working directory
    if cwd:
        parts.append(f"[Working directory: {cwd}]")

    # Session ID for continuity
    session_id = ctx.get("session_id", "")
    if session_id:
        parts.append(f"[Session: {session_id[:8]}...]")

    return "\n\n".join(parts)


def handle_pre_compact(ctx: dict) -> dict | None:
    """Backup transcript before compaction and preserve key context."""
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

    # Build preservation message
    messages = []

    # Key context preservation
    key_context = get_key_context(ctx)
    if key_context:
        messages.append(key_context)

    # Learning reminder
    learnings_dir = Path.home() / ".claude/learnings"
    if learnings_dir.exists():
        categories = [f.stem for f in learnings_dir.glob("*.md") if f.stem != "README"]
        if categories:
            categories_str = ", ".join(categories[:5])
            messages.append(
                f"[Learning Reminder] Before compacting, consider capturing any insights. "
                f"Categories: {categories_str}. "
                f"Format: ## [Date] Title\\n**Context:** ...\\n**Learning:** ...\\n**Application:** ..."
            )

    if messages:
        return {
            "result": "continue",
            "message": "\n\n".join(messages)
        }

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
        result = handle_pre_compact(ctx)
        if result:
            print(json.dumps(result))
    elif tool_name in ("Edit", "Write"):
        # PreToolUse event
        result = handle_pre_tool_use(ctx)
        if result:
            print(json.dumps(result))

    sys.exit(0)


if __name__ == "__main__":
    main()

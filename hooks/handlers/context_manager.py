#!/home/jonglaser/.claude/data/venv/bin/python3
"""
Context Manager Hook - Comprehensive context preservation and monitoring.

Consolidates state_saver.py and context_monitor.py.

Runs on:
- PreToolUse (Edit, Write): Save checkpoint before risky edits
- PostToolUse (Bash): Save error backup when commands fail
- PreCompact: Backup transcript before compaction, preserve key context
- UserPromptSubmit: Monitor token count, warn at thresholds, auto-backup at critical
"""
import json
import sys
from pathlib import Path
from datetime import datetime

from hooks.config import Thresholds
from hooks.hook_utils import (
    graceful_main,
    log_event,
    backup_transcript,
    update_session_state,
    get_session_id,
)
from hooks.hook_sdk import PreToolUseContext, PostToolUseContext, Response

# Import from split modules
from hooks.handlers.checkpoint import (
    load_state,
    is_risky_operation,
    should_checkpoint,
    save_checkpoint_entry,
    save_error_backup,
)
from hooks.handlers.transcript import (
    get_transcript_size,
    get_session_summary,
)

# Configuration
TOKEN_WARNING_THRESHOLD = Thresholds.TOKEN_WARNING
TOKEN_CRITICAL_THRESHOLD = Thresholds.TOKEN_CRITICAL


# ==============================================================================
# Context Preservation
# ==============================================================================

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


def get_active_todos(raw: dict) -> str:
    """Extract active todos from context if present."""
    # Check if there's a todos key in context (from TodoWrite tool state)
    todos = raw.get("todos", [])
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


def get_key_context(raw: dict) -> str:
    """Extract key context that should survive compaction."""
    parts = []
    cwd = raw.get("cwd", "")

    # CLAUDE.md content
    claude_md = get_claude_md_content(cwd)
    if claude_md:
        parts.append(claude_md)

    # Active todos
    todos = get_active_todos(raw)
    if todos:
        parts.append(todos)

    # Current working directory
    if cwd:
        parts.append(f"[Working directory: {cwd}]")

    # Session ID for continuity
    session_id = raw.get("session_id", "")
    if session_id:
        parts.append(f"[Session: {session_id[:8]}...]")

    return "\n\n".join(parts)


# ==============================================================================
# Event Handlers
# ==============================================================================

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
        log_event("context_manager", "checkpoint", {"file": filename, "reason": reason})
        return Response.allow(f"[Checkpoint] {filename} ({reason})")

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
        log_event("context_manager", "error_backup", {
            "command": command[:100],
            "exit_code": exit_code,
            "backup": backup_path
        })

    return None


def handle_pre_compact(raw: dict) -> dict | None:
    """Backup transcript before compaction and preserve key context."""
    transcript_path = raw.get("transcript_path", "")

    if not transcript_path:
        return None

    backup_path = backup_transcript(transcript_path, reason="pre_compact")

    if backup_path:
        update_session_state({
            "last_compact_backup": backup_path,
            "last_compact_time": datetime.now().isoformat()
        })
        log_event("context_manager", "pre_compact_backup", {"backup_path": backup_path})

    # Build preservation message
    messages = []

    # Key context preservation
    key_context = get_key_context(raw)
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


def check_context(raw: dict) -> dict | None:
    """Monitor token count and warn at thresholds (UserPromptSubmit handler)."""
    transcript_path = raw.get('transcript_path', '')
    token_count, message_count = get_transcript_size(transcript_path)

    if token_count >= TOKEN_CRITICAL_THRESHOLD:
        # Pre-compact backup (audit trail)
        if transcript_path:
            backup_path = backup_transcript(transcript_path, "pre_compact")
            if backup_path:
                log_event("context_manager", "pre_compact_backup", {
                    "tokens": token_count,
                    "backup": backup_path
                })

        summary = get_session_summary(transcript_path)
        lines = [f"[Context Monitor] CRITICAL: {token_count:,} tokens ({message_count} msgs)"]
        lines.append("  Transcript backed up automatically.")
        if summary:
            lines.append(f"  Session: {summary}")
        lines.append("  Recommend /compact. Preserve: current task, modified files, errors.")
        return {"message": "\n".join(lines)}

    elif token_count >= TOKEN_WARNING_THRESHOLD:
        return {"message": f"[Context Monitor] {token_count:,} tokens. /compact available if needed."}

    return None


# ==============================================================================
# Standalone Main (for PreCompact event)
# ==============================================================================

@graceful_main("context_manager")
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

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
import heapq
import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path
from datetime import datetime

from hooks.config import Thresholds, Timeouts, Limits, StateSaver, DATA_DIR, CACHE_DIR
from hooks.hook_utils import (
    graceful_main,
    log_event,
    backup_transcript,
    update_session_state,
    get_session_id,
    safe_save_json,
    safe_load_json,
    count_tokens_accurate,
    create_ttl_cache,
    iter_jsonl,
)
from hooks.hook_sdk import PreToolUseContext, PostToolUseContext, Response, HookState

# Configuration
TOKEN_WARNING_THRESHOLD = Thresholds.TOKEN_WARNING
TOKEN_CRITICAL_THRESHOLD = Thresholds.TOKEN_CRITICAL
ERROR_BACKUP_DIR = DATA_DIR / "error-backups"
CHECKPOINT_INTERVAL = Timeouts.CHECKPOINT_INTERVAL
MAX_ERROR_BACKUPS = Thresholds.MAX_ERROR_BACKUPS
CACHE_FILE = CACHE_DIR / "context-cache.json"

# Cache setup
CACHE_DIR.mkdir(parents=True, exist_ok=True)
_token_cache = create_ttl_cache(maxsize=Limits.TOKEN_CACHE_MAXSIZE, ttl=Timeouts.TOKEN_CACHE_TTL)
_TOKEN_CACHE_KEY = "file_cache"

# State management using HookState
_checkpoint_state = HookState("checkpoint", use_session=False)


# =============================================================================
# Checkpoint Functions (inlined from checkpoint.py)
# =============================================================================

def load_state() -> dict:
    """Load checkpoint state using HookState."""
    return _checkpoint_state.load(default={"last_checkpoint": 0, "checkpoints": []})


def save_state(state: dict):
    """Save checkpoint state using HookState."""
    _checkpoint_state.save(state)


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


# =============================================================================
# Transcript Functions (inlined from transcript.py)
# =============================================================================

def load_cache():
    """Load token count cache from disk with in-memory caching."""
    if _TOKEN_CACHE_KEY in _token_cache:
        return _token_cache[_TOKEN_CACHE_KEY]
    data = safe_load_json(CACHE_FILE, {})
    _token_cache[_TOKEN_CACHE_KEY] = data
    return data


def save_cache(cache):
    """Save token count cache to disk and update in-memory cache."""
    _token_cache[_TOKEN_CACHE_KEY] = cache
    safe_save_json(CACHE_FILE, cache)


def get_cached_count(transcript_path):
    """Check cache for valid token count.

    Returns:
        (tokens, messages, offset, can_increment) or None
        - can_increment: True if we can do incremental scan from offset
    """
    cache = load_cache()
    cached = cache.get("transcript")
    if not cached or cached.get("path") != transcript_path:
        return None
    try:
        stat = os.stat(transcript_path)
        cached_size = cached.get("size", 0)
        cached_offset = cached.get("offset", 0)

        # Exact match - file unchanged
        if cached.get("mtime") == stat.st_mtime and cached_size == stat.st_size:
            return cached.get("tokens", 0), cached.get("messages", 0), cached_offset, False

        # File grew - can do incremental scan from last offset
        if stat.st_size > cached_size and cached_offset > 0:
            return cached.get("tokens", 0), cached.get("messages", 0), cached_offset, True

    except OSError:
        pass
    return None


def update_cache(transcript_path, tokens, messages, offset):
    """Update cache with new token count and file offset."""
    try:
        stat = os.stat(transcript_path)
        cache = {
            "transcript": {
                "path": transcript_path,
                "mtime": stat.st_mtime,
                "size": stat.st_size,
                "tokens": tokens,
                "messages": messages,
                "offset": offset
            }
        }
        save_cache(cache)
    except OSError:
        pass


def _count_tokens_in_entry(entry: dict) -> int:
    """Count tokens in a transcript entry."""
    tokens = 0
    if 'content' in entry:
        content = entry['content']
        if isinstance(content, str):
            tokens += count_tokens_accurate(content)
        elif isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and 'text' in item:
                    tokens += count_tokens_accurate(item['text'])
    return tokens


def get_transcript_size(transcript_path):
    """Read transcript and count tokens accurately, with incremental caching."""
    if not transcript_path or not os.path.exists(transcript_path):
        return 0, 0

    # Check cache first
    cached = get_cached_count(transcript_path)
    if cached:
        tokens, messages, offset, can_increment = cached
        if not can_increment:
            # File unchanged, return cached values
            return tokens, messages

        # Incremental scan from last offset
        try:
            with open(transcript_path, 'r') as f:
                f.seek(offset)
                new_tokens = 0
                new_messages = 0
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        new_tokens += _count_tokens_in_entry(entry)
                        new_messages += 1
                    except json.JSONDecodeError:
                        continue
                new_offset = f.tell()

            total_tokens = tokens + new_tokens
            total_messages = messages + new_messages
            update_cache(transcript_path, total_tokens, total_messages, new_offset)
            return total_tokens, total_messages
        except (OSError, PermissionError):
            pass  # Fall through to full scan

    # Fast path: check file size first (avoid full scan for small files)
    # ~4 bytes per token on average, 40K tokens ≈ 160KB
    try:
        file_size = os.path.getsize(transcript_path)
        if file_size < 160 * 1024:  # Under 160KB, estimate without full scan
            estimated_tokens = file_size // 4
            estimated_messages = file_size // 500
            return estimated_tokens, estimated_messages
    except OSError:
        pass

    # Full scan with accurate token counting for large files
    total_tokens = 0
    message_count = 0

    try:
        with open(transcript_path, 'r') as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    total_tokens += _count_tokens_in_entry(entry)
                    message_count += 1
                except json.JSONDecodeError:
                    continue
            final_offset = f.tell()
    except (OSError, PermissionError):
        return 0, 0

    # Cache the result with file offset for incremental updates
    update_cache(transcript_path, total_tokens, message_count, final_offset)

    return total_tokens, message_count


def _get_cached_summary(transcript_path):
    """Check cache for valid session summary state.

    Returns:
        (summary_state, offset, can_increment) or None
        - summary_state: dict with files_edited, files_written, tool_counts, error_count
        - can_increment: True if we can do incremental scan from offset
    """
    cache = load_cache()
    cached = cache.get("summary")
    if not cached or cached.get("path") != transcript_path:
        return None
    try:
        stat = os.stat(transcript_path)
        cached_size = cached.get("size", 0)
        cached_offset = cached.get("offset", 0)

        # Exact match - file unchanged
        if cached.get("mtime") == stat.st_mtime and cached_size == stat.st_size:
            return cached.get("state"), cached_offset, False

        # File grew - can do incremental scan from last offset
        if stat.st_size > cached_size and cached_offset > 0:
            return cached.get("state"), cached_offset, True
    except OSError:
        pass
    return None


def _update_summary_cache(transcript_path, state, offset):
    """Update cache with session summary state."""
    try:
        stat = os.stat(transcript_path)
        cache = load_cache()
        cache["summary"] = {
            "path": transcript_path,
            "mtime": stat.st_mtime,
            "size": stat.st_size,
            "state": state,
            "offset": offset
        }
        save_cache(cache)
    except OSError:
        pass


def _process_summary_entry(entry: dict, files_edited: set, files_written: set, tool_counts: dict):
    """Process a single transcript entry for summary extraction."""
    tool = entry.get("tool_name", "")
    if tool:
        tool_counts[tool] += 1
        tool_input = entry.get("tool_input", {})
        path = tool_input.get("file_path", "")
        if tool == "Edit" and path:
            files_edited.add(Path(path).name)
        elif tool == "Write" and path:
            files_written.add(Path(path).name)


def get_session_summary(transcript_path):
    """Generate brief summary of session activity for compaction guidance.

    Uses incremental caching - only processes new entries since last call.
    """
    if not transcript_path or not os.path.exists(transcript_path):
        return ""

    # Check cache for incremental processing
    files_edited = set()
    files_written = set()
    tool_counts = defaultdict(int)
    error_count = 0
    start_offset = 0

    cached = _get_cached_summary(transcript_path)
    if cached:
        state, offset, can_increment = cached
        if state and not can_increment:
            # Cache is valid and file unchanged - rebuild summary from state
            files_edited = set(state.get("files_edited", []))
            files_written = set(state.get("files_written", []))
            tool_counts = defaultdict(int, state.get("tool_counts", {}))
            error_count = state.get("error_count", 0)
        elif state and can_increment:
            # Incremental update from last offset
            files_edited = set(state.get("files_edited", []))
            files_written = set(state.get("files_written", []))
            tool_counts = defaultdict(int, state.get("tool_counts", {}))
            error_count = state.get("error_count", 0)
            start_offset = offset

    # Process transcript (from start or incrementally)
    # Note: incremental processing requires file offset tracking which iter_jsonl
    # doesn't support directly. For now, we do a full scan when cache is invalid.
    # TODO: Consider adding offset support to iter_jsonl for large transcripts.
    try:
        if start_offset > 0:
            # Incremental: read from offset manually
            with open(transcript_path, 'r') as f:
                f.seek(start_offset)
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        _process_summary_entry(entry, files_edited, files_written, tool_counts)
                        content = str(entry.get("content", ""))
                        if "error" in content.lower() or "failed" in content.lower():
                            error_count += 1
                    except json.JSONDecodeError:
                        continue
                final_offset = f.tell()
        else:
            # Full scan using iter_jsonl
            for entry in iter_jsonl(transcript_path):
                _process_summary_entry(entry, files_edited, files_written, tool_counts)
                content = str(entry.get("content", ""))
                if "error" in content.lower() or "failed" in content.lower():
                    error_count += 1
            # Get final offset
            final_offset = os.path.getsize(transcript_path)
    except (OSError, PermissionError):
        return ""

    # Update cache with current state
    state = {
        "files_edited": list(files_edited),
        "files_written": list(files_written),
        "tool_counts": dict(tool_counts),
        "error_count": error_count
    }
    _update_summary_cache(transcript_path, state, final_offset)

    # Build compact summary
    parts = []
    if files_edited:
        parts.append(f"Edited: {', '.join(sorted(files_edited)[:5])}")
    if files_written:
        parts.append(f"Created: {', '.join(sorted(files_written)[:3])}")
    if error_count > 0:
        parts.append(f"Errors: {error_count}")

    # Top 3 tools
    top_tools = heapq.nlargest(3, tool_counts.items(), key=lambda x: x[1])
    if top_tools:
        tools_str = ", ".join(f"{t}:{c}" for t, c in top_tools)
        parts.append(f"Tools: {tools_str}")

    return " | ".join(parts) if parts else ""


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

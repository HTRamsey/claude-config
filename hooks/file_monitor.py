#!/home/jonglaser/.claude/data/venv/bin/python3
"""
File Monitor - Unified file access tracking and pre-read analysis.

Consolidates:
- file_access_tracker: Track reads, detect stale context, duplicate searches
- preread_summarize: Suggest summarization for large files

Uses centralized session state via hook_utils.
"""
import hashlib
import json
import sys
import time
from pathlib import Path

from hook_utils import (
    graceful_main,
    get_session_id,
    is_post_tool_use,
    normalize_path,
    safe_mtime,
    safe_stat,
    safe_exists,
)
from hook_utils.state import StateManager
from hook_sdk import PreToolUseContext, PostToolUseContext, Response
from config import Thresholds, Timeouts, FilePatterns

# ============================================================================
# Configuration (imported from config.py)
# ============================================================================

STATE_NAMESPACE = "file_monitor"
MAX_AGE_SECONDS = Timeouts.STATE_MAX_AGE  # Clear state after 24 hours
STALE_MESSAGE_THRESHOLD = Thresholds.STALE_MESSAGE_THRESHOLD  # Warn if file was read >15 messages ago
STALE_TIME_THRESHOLD = Timeouts.STALE_TIME_THRESHOLD  # Or >5 minutes ago
SIMILARITY_THRESHOLD = Thresholds.SIMILARITY_THRESHOLD  # For fuzzy pattern matching

# State pruning limits (from centralized config)
MAX_READS = Thresholds.MAX_READS_TRACKED
MAX_SEARCHES = Thresholds.MAX_SEARCHES_TRACKED

# Large file thresholds (from centralized config)
LARGE_FILE_LINES = Thresholds.LARGE_FILE_LINES
LARGE_FILE_BYTES = Thresholds.LARGE_FILE_BYTES
ALWAYS_SUMMARIZE_EXTENSIONS = FilePatterns.ALWAYS_SUMMARIZE
SKIP_EXTENSIONS = FilePatterns.SKIP_SUMMARIZE

# ============================================================================
# Shared State Management (via StateManager)
# ============================================================================

# Initialize StateManager for this hook
_state_manager = StateManager(namespace=STATE_NAMESPACE, use_session=True)


def load_state(session_id: str) -> dict:
    """Load unified state for session using StateManager."""
    default = {
        "reads": {},
        "searches": {},
        "message_count": 0,
    }
    return _state_manager.load_with_ttl(
        session_id=session_id,
        default=default,
        max_age_secs=MAX_AGE_SECONDS
    )


def save_state(session_id: str, state: dict):
    """Save unified state with automatic pruning via StateManager."""
    _state_manager.save_with_pruning(
        state,
        session_id=session_id,
        max_entries=MAX_READS,
        items_key="reads",
        time_key="time"
    )

# ============================================================================
# Shared Utilities
# ============================================================================

def check_file_modified(file_path: str, read_time: float) -> bool:
    """Check if file was modified after it was read."""
    mtime = safe_mtime(file_path, default=0.0)
    return mtime > read_time if mtime > 0 else False

def hash_search(tool_name: str, pattern: str, path: str) -> str:
    """Create hash for search operation."""
    key = f"{tool_name}:{pattern}:{path}"
    return hashlib.md5(key.encode()).hexdigest()[:12]

def normalize_pattern(pattern: str) -> str:
    """Normalize pattern for comparison."""
    return pattern.lower().strip()

def check_similar_patterns(new_pattern: str, existing_patterns: list) -> str | None:
    """Check if a similar pattern was already searched."""
    new_norm = normalize_pattern(new_pattern)
    for existing in existing_patterns:
        existing_norm = normalize_pattern(existing)
        if new_norm == existing_norm:
            return existing
        if new_norm in existing_norm or existing_norm in new_norm:
            return existing
        new_words = set(new_norm.split())
        existing_words = set(existing_norm.split())
        if new_words and existing_words:
            overlap = len(new_words & existing_words) / max(len(new_words), len(existing_words))
            if overlap >= SIMILARITY_THRESHOLD:
                return existing
    return None

# ============================================================================
# Large File Detection (from preread_summarize)
# ============================================================================

def count_lines_fast(file_path: Path) -> int:
    """Fast line count using buffer reading."""
    try:
        with open(file_path, 'rb') as f:
            return sum(1 for _ in f)
    except (OSError, PermissionError):
        return 0

def check_large_file(file_path: str, limit: int | None) -> tuple[bool, str]:
    """Determine if file should be summarized first."""
    path = Path(file_path)

    if not safe_exists(file_path):
        return False, ""

    if limit and limit < LARGE_FILE_LINES:
        return False, ""

    ext = path.suffix.lower()
    if ext in SKIP_EXTENSIONS:
        return False, ""

    stat = safe_stat(file_path)
    if not stat:
        return False, ""

    size = stat.st_size
    if size < LARGE_FILE_BYTES:
        return False, ""

    lines = count_lines_fast(path)
    if lines <= LARGE_FILE_LINES:
        return False, ""

    size_kb = size / 1024
    reason = f"{lines} lines, {size_kb:.1f}KB"

    if ext in ALWAYS_SUMMARIZE_EXTENSIONS:
        reason += f" ({ext} file - consider extracting specific fields)"

    return True, reason

# ============================================================================
# PreToolUse Handlers
# ============================================================================

def handle_read_pre(ctx: PreToolUseContext, state: dict) -> list[str]:
    """Handle Read PreToolUse - track read and check for large files."""
    file_path = ctx.tool_input.file_path
    limit = ctx.tool_input.get("limit")
    messages = []

    if not file_path:
        return messages

    # Track the read
    norm_path = normalize_path(file_path)
    state["reads"][norm_path] = {
        "time": time.time(),
        "message_num": state["message_count"],
        "path": file_path,
        "count": state["reads"].get(norm_path, {}).get("count", 0)
    }

    # Check for large file
    is_large, reason = check_large_file(file_path, limit)
    if is_large:
        filename = Path(file_path).name
        messages.append(f"[Large File] {filename}: {reason}")
        messages.append("  → Consider: Task(quick-lookup) or smart-view.sh first")

    return messages

def handle_edit_pre(ctx: PreToolUseContext, state: dict) -> list[str]:
    """Handle Edit PreToolUse - check for stale context."""
    file_path = ctx.tool_input.file_path
    messages = []

    if not file_path:
        return messages

    norm_path = normalize_path(file_path)
    read_info = state["reads"].get(norm_path)

    if not read_info:
        messages.append("[Stale Context] File was not read in this session")
        messages.append(f"  Consider reading {Path(file_path).name} before editing")
    else:
        read_time = read_info.get("time", 0)
        read_msg = read_info.get("message_num", 0)
        current_msg = state["message_count"]
        messages_ago = current_msg - read_msg
        seconds_ago = time.time() - read_time

        if check_file_modified(file_path, read_time):
            messages.append("[Stale Context] File modified on disk since last read")
            messages.append(f"  Re-read {Path(file_path).name} to get current content")
        elif messages_ago > STALE_MESSAGE_THRESHOLD:
            messages.append(f"[Stale Context] File read {messages_ago} messages ago")
            messages.append(f"  Consider re-reading {Path(file_path).name}")
        elif seconds_ago > STALE_TIME_THRESHOLD:
            minutes_ago = int(seconds_ago / 60)
            messages.append(f"[Stale Context] File read {minutes_ago} minutes ago")

    return messages

def track_file_pre(raw: dict) -> dict | None:
    """Combined PreToolUse handler for Read and Edit."""
    ctx = PreToolUseContext(raw)
    session_id = get_session_id(raw)
    state = load_state(session_id)
    state["message_count"] = state.get("message_count", 0) + 1

    messages = []

    if ctx.tool_name == "Read":
        messages = handle_read_pre(ctx, state)
    elif ctx.tool_name == "Edit":
        messages = handle_edit_pre(ctx, state)

    save_state(session_id, state)

    if messages:
        return Response.allow("\n".join(messages))
    return None

# ============================================================================
# PostToolUse Handlers
# ============================================================================

def handle_search_post(ctx: PostToolUseContext, state: dict) -> str | None:
    """Handle Grep/Glob PostToolUse - detect duplicate searches."""
    pattern = ctx.tool_input.pattern
    path = ctx.tool_input.get("path", ".")

    if not pattern:
        return None

    search_hash = hash_search(ctx.tool_name, pattern, path)

    if search_hash in state["searches"]:
        prev = state["searches"][search_hash]
        message = f"[Duplicate] Same {ctx.tool_name} search performed {prev['count']} time(s) before"
        prev["count"] += 1
        return message

    all_patterns = [v["pattern"] for v in state["searches"].values()]
    similar = check_similar_patterns(pattern, all_patterns)
    if similar:
        message = f"[Similar Search] Previously searched: '{similar}'"
    else:
        message = None

    state["searches"][search_hash] = {
        "pattern": pattern,
        "path": path,
        "tool": ctx.tool_name,
        "count": 1,
        "time": time.time()
    }

    return message

def handle_read_post(ctx: PostToolUseContext, state: dict) -> str | None:
    """Handle Read PostToolUse - detect duplicate reads."""
    file_path = ctx.tool_input.file_path

    if not file_path:
        return None

    norm_path = normalize_path(file_path)
    read_info = state["reads"].get(norm_path, {})
    count = read_info.get("count", 0) + 1

    if norm_path in state["reads"]:
        state["reads"][norm_path]["count"] = count
    else:
        state["reads"][norm_path] = {
            "time": time.time(),
            "message_num": state.get("message_count", 0),
            "path": file_path,
            "count": count
        }

    if count >= 2:
        return f"[Duplicate Read] File read {count} times this session"

    return None

def track_file_post(raw: dict) -> dict | None:
    """Combined PostToolUse handler for Grep, Glob, Read."""
    ctx = PostToolUseContext(raw)
    session_id = get_session_id(raw)
    state = load_state(session_id)

    message = None

    if ctx.tool_name in ("Grep", "Glob"):
        message = handle_search_post(ctx, state)
    elif ctx.tool_name == "Read":
        message = handle_read_post(ctx, state)

    save_state(session_id, state)

    if message:
        total_searches = len(state["searches"])
        total_reads = len(state["reads"])
        dup_searches = sum(1 for s in state["searches"].values() if s.get("count", 1) > 1)
        dup_reads = sum(1 for r in state["reads"].values() if r.get("count", 1) > 1)

        stats = f"Session: {total_searches} searches, {total_reads} reads"
        if dup_searches or dup_reads:
            stats += f" ({dup_searches} dup searches, {dup_reads} dup reads)"

        return Response.message(f"{message}\n  {stats}")

    return None

# ============================================================================
# Main
# ============================================================================

@graceful_main("file_monitor")
def main():
    try:
        ctx = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    if is_post_tool_use(ctx):
        result = track_file_post(ctx)
        if result:
            msg = result.get("hookSpecificOutput", {}).get("message", "")
            print(msg)
    else:
        result = track_file_pre(ctx)
        if result:
            print(json.dumps(result))

    sys.exit(0)


if __name__ == "__main__":
    main()

#!/home/jonglaser/.claude/venv/bin/python3
"""
Unified File Access Tracker Hook - Combines stale context detection and duplicate search detection.

Runs on:
- PreToolUse (Read, Edit): Track reads, warn on stale edits
- PostToolUse (Grep, Glob, Read): Warn on duplicate searches/reads

Consolidates functionality from:
- stale_context_detector.py
- duplicate_search_detector.py

This reduces hook overhead from 2 Python processes to 1.
"""
import json
import hashlib
import os
import sys
import time
from pathlib import Path

# Import shared utilities
sys.path.insert(0, str(Path(__file__).parent))
try:
    from hook_utils import graceful_main, log_event
    HAS_UTILS = True
except ImportError:
    HAS_UTILS = False
    def graceful_main(name):
        def decorator(func):
            return func
        return decorator
    def log_event(*args, **kwargs):
        pass

# Configuration
STATE_DIR = Path("/tmp/claude-file-tracker")
MAX_AGE_SECONDS = 3600  # Clear state after 1 hour
STALE_MESSAGE_THRESHOLD = 15  # Warn if file was read >15 messages ago
STALE_TIME_THRESHOLD = 300  # Or >5 minutes ago
SIMILARITY_THRESHOLD = 0.8  # For fuzzy pattern matching

def get_state_file(session_id: str) -> Path:
    """Get session-specific state file path."""
    STATE_DIR.mkdir(exist_ok=True)
    return STATE_DIR / f"tracker_{session_id}.json"

def load_state(session_id: str) -> dict:
    """Load unified state for session."""
    state_file = get_state_file(session_id)
    default = {
        "reads": {},
        "searches": {},
        "message_count": 0,
        "last_update": time.time()
    }
    if state_file.exists():
        try:
            with open(state_file) as f:
                state = json.load(f)
                if time.time() - state.get("last_update", 0) > MAX_AGE_SECONDS:
                    return default
                return state
        except (json.JSONDecodeError, IOError):
            pass
    return default

def save_state(session_id: str, state: dict):
    """Save unified state."""
    state["last_update"] = time.time()
    state_file = get_state_file(session_id)
    try:
        with open(state_file, "w") as f:
            json.dump(state, f)
    except IOError:
        pass

def normalize_path(path: str) -> str:
    """Normalize file path for comparison."""
    try:
        return str(Path(path).resolve())
    except Exception:
        return path

def check_file_modified(file_path: str, read_time: float) -> bool:
    """Check if file was modified after it was read."""
    try:
        mtime = os.path.getmtime(file_path)
        return mtime > read_time
    except OSError:
        return False

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

def handle_pre_tool_use(ctx: dict, state: dict) -> dict | None:
    """Handle PreToolUse events (Read, Edit)."""
    tool_name = ctx.get("tool_name", "")
    tool_input = ctx.get("tool_input", {})

    state["message_count"] = state.get("message_count", 0) + 1

    if tool_name == "Read":
        file_path = tool_input.get("file_path", "")
        if file_path:
            norm_path = normalize_path(file_path)
            state["reads"][norm_path] = {
                "time": time.time(),
                "message_num": state["message_count"],
                "path": file_path
            }
        return None

    elif tool_name == "Edit":
        file_path = tool_input.get("file_path", "")
        if not file_path:
            return None

        norm_path = normalize_path(file_path)
        read_info = state["reads"].get(norm_path)
        messages = []

        if not read_info:
            messages.append(f"[Stale Context] File was not read in this session")
            messages.append(f"  Consider reading {Path(file_path).name} before editing")
        else:
            read_time = read_info.get("time", 0)
            read_msg = read_info.get("message_num", 0)
            current_msg = state["message_count"]
            messages_ago = current_msg - read_msg
            seconds_ago = time.time() - read_time

            if check_file_modified(file_path, read_time):
                messages.append(f"[Stale Context] File modified on disk since last read")
                messages.append(f"  Re-read {Path(file_path).name} to get current content")
            elif messages_ago > STALE_MESSAGE_THRESHOLD:
                messages.append(f"[Stale Context] File read {messages_ago} messages ago")
                messages.append(f"  Consider re-reading {Path(file_path).name}")
            elif seconds_ago > STALE_TIME_THRESHOLD:
                minutes_ago = int(seconds_ago / 60)
                messages.append(f"[Stale Context] File read {minutes_ago} minutes ago")

        if messages:
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "allow",
                    "permissionDecisionReason": "\n".join(messages)
                }
            }

    return None

def handle_post_tool_use(ctx: dict, state: dict) -> str | None:
    """Handle PostToolUse events (Grep, Glob, Read)."""
    tool_name = ctx.get("tool_name", "")
    tool_input = ctx.get("tool_input", {})
    message = None

    if tool_name in ("Grep", "Glob"):
        pattern = tool_input.get("pattern", "")
        path = tool_input.get("path", ".")

        if pattern:
            search_hash = hash_search(tool_name, pattern, path)

            if search_hash in state["searches"]:
                prev = state["searches"][search_hash]
                message = f"[Duplicate] Same {tool_name} search performed {prev['count']} time(s) before"
                prev["count"] += 1
            else:
                all_patterns = [v["pattern"] for v in state["searches"].values()]
                similar = check_similar_patterns(pattern, all_patterns)
                if similar:
                    message = f"[Similar Search] Previously searched: '{similar}'"

                state["searches"][search_hash] = {
                    "pattern": pattern,
                    "path": path,
                    "tool": tool_name,
                    "count": 1,
                    "time": time.time()
                }

    elif tool_name == "Read":
        file_path = tool_input.get("file_path", "")
        norm_path = normalize_path(file_path) if file_path else ""

        if norm_path:
            read_info = state["reads"].get(norm_path, {})
            count = read_info.get("count", 0) + 1
            if count >= 2:
                message = f"[Duplicate Read] File read {count} times this session"

            # Update read info with count
            if norm_path in state["reads"]:
                state["reads"][norm_path]["count"] = count
            else:
                state["reads"][norm_path] = {
                    "time": time.time(),
                    "message_num": state.get("message_count", 0),
                    "path": file_path,
                    "count": count
                }

    return message

@graceful_main("file_access_tracker")
def main():
    try:
        ctx = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    session_id = ctx.get("session_id", "default")

    state = load_state(session_id)

    # Detect pre/post based on presence of tool_result (PostToolUse has it, PreToolUse doesn't)
    if "tool_result" in ctx:
        # PostToolUse
        message = handle_post_tool_use(ctx, state)
        save_state(session_id, state)
        if message:
            total_searches = len(state["searches"])
            total_reads = len(state["reads"])
            dup_searches = sum(1 for s in state["searches"].values() if s.get("count", 1) > 1)
            dup_reads = sum(1 for r in state["reads"].values() if r.get("count", 1) > 1)

            stats = f"Session: {total_searches} searches, {total_reads} reads"
            if dup_searches or dup_reads:
                stats += f" ({dup_searches} dup searches, {dup_reads} dup reads)"

            print(f"{message}")
            print(f"  {stats}")
    else:
        # PreToolUse
        result = handle_pre_tool_use(ctx, state)
        save_state(session_id, state)
        if result:
            print(json.dumps(result))

    sys.exit(0)

if __name__ == "__main__":
    main()

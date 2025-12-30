#!/home/jonglaser/.claude/data/venv/bin/python3
"""
Batch Operation Detector Hook - Detects repetitive edit patterns.
Runs on PostToolUse for Edit|Write to suggest batching similar operations.

Uses centralized session state via hook_utils.
"""
import json
import os
import re
import sys
import time
from pathlib import Path

# Import shared utilities
sys.path.insert(0, str(Path(__file__).parent))
from hook_utils import (
    graceful_main,
    log_event,
    get_session_id,
    read_session_state,
    write_session_state,
    cleanup_old_sessions,
)
from config import Thresholds, Timeouts

# Configuration (imported from config.py)
STATE_NAMESPACE = "batch_detector"
MAX_AGE_SECONDS = Timeouts.STATE_MAX_AGE  # Clear state after 24 hours
SIMILARITY_THRESHOLD = Thresholds.BATCH_SIMILARITY_THRESHOLD  # Suggest batching after 3 similar ops
CLEANUP_INTERVAL = Timeouts.CLEANUP_INTERVAL  # Rate-limit cleanup to every 5 minutes

# Pre-compiled regex for normalize_content
_WHITESPACE_RE = re.compile(r'\s+')

# Rate limiting for cleanup
_last_cleanup_time = 0


def load_state(session_id: str) -> dict:
    """Load edit history state for session using centralized session state."""
    default = {"edits": [], "writes": [], "last_update": time.time()}
    state = read_session_state(STATE_NAMESPACE, session_id, default)
    if time.time() - state.get("last_update", 0) > MAX_AGE_SECONDS:
        return default
    return state


def save_state(session_id: str, state: dict):
    """Save edit history state using centralized session state."""
    state["last_update"] = time.time()
    write_session_state(STATE_NAMESPACE, state, session_id)


def maybe_cleanup_old_sessions():
    """Trigger cleanup of old session files (rate-limited)."""
    global _last_cleanup_time
    now = time.time()

    if now - _last_cleanup_time < CLEANUP_INTERVAL:
        return
    _last_cleanup_time = now

    # Use centralized cleanup
    cleanup_old_sessions(max_age_secs=MAX_AGE_SECONDS)

def normalize_content(content: str) -> str:
    """Normalize content for comparison (remove whitespace variations)."""
    return _WHITESPACE_RE.sub(' ', content.strip().lower())

def extract_pattern(old_string: str, new_string: str) -> dict:
    """Extract the transformation pattern from an edit."""
    return {
        "old_normalized": normalize_content(old_string),
        "new_normalized": normalize_content(new_string),
        "old_len": len(old_string),
        "new_len": len(new_string),
        "is_rename": old_string.replace(" ", "") != new_string.replace(" ", ""),
    }

def find_similar_edits(current: dict, history: list) -> list:
    """Find edits with similar patterns."""
    similar = []
    curr_pattern = current.get("pattern", {})

    for edit in history:
        hist_pattern = edit.get("pattern", {})

        # Check for similar transformations
        if curr_pattern.get("old_normalized") == hist_pattern.get("old_normalized"):
            similar.append(edit)
        elif curr_pattern.get("new_normalized") == hist_pattern.get("new_normalized"):
            similar.append(edit)
        # Check for same type of operation (similar size changes)
        elif (abs(curr_pattern.get("old_len", 0) - hist_pattern.get("old_len", 0)) < 20 and
              abs(curr_pattern.get("new_len", 0) - hist_pattern.get("new_len", 0)) < 20 and
              curr_pattern.get("is_rename") == hist_pattern.get("is_rename")):
            # Check if it's likely the same transformation
            if curr_pattern.get("old_normalized", "")[:30] == hist_pattern.get("old_normalized", "")[:30]:
                similar.append(edit)

    return similar

def get_file_extension(path: str) -> str:
    """Get file extension for grouping."""
    return Path(path).suffix.lower()

def suggest_batch_command(edits: list, current_edit: dict) -> str:
    """Generate a suggestion for batching similar edits."""
    all_edits = edits + [current_edit]
    files = [e["file"] for e in all_edits]
    extensions = set(get_file_extension(f) for f in files)

    # Get common directory
    try:
        common_dir = os.path.commonpath(files)
    except ValueError:
        common_dir = "."

    # Build glob pattern
    if len(extensions) == 1:
        ext = list(extensions)[0]
        glob_pattern = f"{common_dir}/**/*{ext}"
    else:
        glob_pattern = f"{common_dir}/**/*"

    old_str = current_edit.get("old_string", "")[:30]
    new_str = current_edit.get("new_string", "")[:30]

    if old_str and new_str:
        return f"sd '{old_str}' '{new_str}' '{glob_pattern}'"
    return f"code-mode batch edit across {glob_pattern}"

def detect_batch(ctx: dict) -> dict | None:
    """Handler function for dispatcher. Returns result dict or None."""
    tool_name = ctx.get("tool_name", "")
    tool_input = ctx.get("tool_input", {})
    session_id = get_session_id(ctx)

    if tool_name not in ("Edit", "Write"):
        return None

    # Periodically clean up old session files
    maybe_cleanup_old_sessions()

    state = load_state(session_id)
    message = None

    if tool_name == "Edit":
        file_path = tool_input.get("file_path", "")
        old_string = tool_input.get("old_string", "")
        new_string = tool_input.get("new_string", "")

        if file_path and old_string and new_string:
            current_edit = {
                "file": file_path,
                "old_string": old_string,
                "new_string": new_string,
                "pattern": extract_pattern(old_string, new_string),
                "time": time.time()
            }

            # Find similar edits
            similar = find_similar_edits(current_edit, state["edits"])

            if len(similar) >= SIMILARITY_THRESHOLD - 1:
                # We have enough similar edits to suggest batching
                suggestion = suggest_batch_command(similar, current_edit)
                affected_files = [e["file"] for e in similar] + [file_path]
                unique_files = list(set(Path(f).name for f in affected_files))

                message = f"[Batch Detector] {len(similar) + 1} similar edits detected"
                message += f"\n  Files: {', '.join(unique_files[:5])}"
                if len(unique_files) > 5:
                    message += f" (+{len(unique_files) - 5} more)"
                message += f"\n  → Use: Task(batch-editor, '{suggestion}')"
                message += f"\n  → Or:  {suggestion}"

                log_event("batch_operation_detector", "batch_suggestion", {"count": len(similar) + 1, "files": len(unique_files)})

            # Store this edit
            state["edits"].append(current_edit)
            state["edits"] = state["edits"][-50:]

    elif tool_name == "Write":
        file_path = tool_input.get("file_path", "")
        content = tool_input.get("content", "")

        if file_path and content:
            current_write = {
                "file": file_path,
                "content_hash": hash(content[:200]),
                "extension": get_file_extension(file_path),
                "size": len(content),
                "time": time.time()
            }

            similar_writes = [
                w for w in state["writes"]
                if w["extension"] == current_write["extension"]
                and abs(w["size"] - current_write["size"]) < 500
            ]

            if len(similar_writes) >= SIMILARITY_THRESHOLD - 1:
                files = [w["file"] for w in similar_writes] + [file_path]
                unique_files = list(set(Path(f).name for f in files))

                message = f"[Batch Detector] {len(similar_writes) + 1} similar file creations"
                message += f"\n  Files: {', '.join(unique_files[:5])}"
                message += "\n  Consider: code-mode batch write or template generation"

                log_event("batch_operation_detector", "batch_write_suggestion", {"count": len(similar_writes) + 1, "files": len(unique_files)})

            state["writes"].append(current_write)
            state["writes"] = state["writes"][-50:]

    save_state(session_id, state)

    if message:
        return {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "message": message
            }
        }

    return None


@graceful_main("batch_operation_detector")
def main():
    try:
        ctx = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    result = detect_batch(ctx)
    if result:
        msg = result.get("hookSpecificOutput", {}).get("message", "")
        print(msg)

    sys.exit(0)


if __name__ == "__main__":
    main()

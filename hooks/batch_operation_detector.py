#!/home/jonglaser/.claude/venv/bin/python3
"""
Batch Operation Detector Hook - Detects repetitive edit patterns.
Runs on PostToolUse for Edit|Write to suggest batching similar operations.

Tracks operations in a session-specific temp file.
"""
import json
import os
import re
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
STATE_DIR = Path("/tmp/claude-batch-state")
MAX_AGE_SECONDS = 3600  # Clear state after 1 hour
SIMILARITY_THRESHOLD = 3  # Suggest batching after 3 similar ops

def get_state_file(session_id: str) -> Path:
    """Get session-specific state file path."""
    STATE_DIR.mkdir(exist_ok=True)
    return STATE_DIR / f"edits_{session_id}.json"

def load_state(session_id: str) -> dict:
    """Load edit history state for session."""
    state_file = get_state_file(session_id)
    if state_file.exists():
        try:
            with open(state_file) as f:
                state = json.load(f)
                if time.time() - state.get("last_update", 0) > MAX_AGE_SECONDS:
                    return {"edits": [], "writes": [], "last_update": time.time()}
                return state
        except (json.JSONDecodeError, IOError):
            pass
    return {"edits": [], "writes": [], "last_update": time.time()}

def save_state(session_id: str, state: dict):
    """Save edit history state."""
    state["last_update"] = time.time()
    state_file = get_state_file(session_id)
    try:
        with open(state_file, "w") as f:
            json.dump(state, f)
    except IOError:
        pass

def normalize_content(content: str) -> str:
    """Normalize content for comparison (remove whitespace variations)."""
    return re.sub(r'\s+', ' ', content.strip().lower())

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

@graceful_main("batch_operation_detector")
def main():
    try:
        ctx = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = ctx.get("tool_name", "")
    tool_input = ctx.get("tool_input", {})
    session_id = ctx.get("session_id", "default")

    if tool_name not in ("Edit", "Write"):
        sys.exit(0)

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
            # Keep only last 50 edits
            state["edits"] = state["edits"][-50:]

    elif tool_name == "Write":
        file_path = tool_input.get("file_path", "")
        content = tool_input.get("content", "")

        if file_path and content:
            current_write = {
                "file": file_path,
                "content_hash": hash(content[:200]),  # Hash first 200 chars
                "extension": get_file_extension(file_path),
                "size": len(content),
                "time": time.time()
            }

            # Check for similar writes (same extension, similar size)
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
        print(message)

    sys.exit(0)

if __name__ == "__main__":
    main()

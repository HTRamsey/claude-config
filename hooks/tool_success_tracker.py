#!/home/jonglaser/.claude/data/venv/bin/python3
"""
Tool Success Tracker Hook - Tracks tool failures and suggests alternatives.
Runs on PostToolUse to monitor errors and recommend better approaches.

Uses centralized session state via hook_utils.
"""
import json
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
)

# Configuration
STATE_NAMESPACE = "tool_tracker"
MAX_AGE_SECONDS = 3600  # Clear state after 1 hour
FAILURE_THRESHOLD = 2  # Suggest alternative after 2 failures

# Error patterns and their suggested fixes - pre-compiled for performance
_ERROR_PATTERNS_RAW = {
    r"old_string.*not found|not unique|no match": {
        "tool": "Edit",
        "suggestion": "Re-read the file to get current content, or use Read tool first",
        "action": "read_first"
    },
    r"file.*not found|no such file": {
        "tool": "*",
        "suggestion": "Check file path with: smart-find.sh <pattern> .",
        "action": "find_file"
    },
    r"permission denied|access denied|not permitted": {
        "tool": "*",
        "suggestion": "Check file permissions or try Task(subagent_type=Explore) for read-only exploration",
        "action": "check_perms"
    },
    r"no matches|no results|pattern not found": {
        "tool": "Grep",
        "suggestion": "Try broader pattern or use Task(subagent_type=Explore) for fuzzy search",
        "action": "broaden_search"
    },
    r"build failed|compilation error|make.*error": {
        "tool": "Bash",
        "suggestion": "Pipe through compress.sh --type build to focus on errors",
        "action": "compress_output"
    },
    r"test.*failed|assertion.*error|pytest.*failed": {
        "tool": "Bash",
        "suggestion": "Pipe through compress.sh --type tests to focus on failures",
        "action": "compress_output"
    },
    r"conflict|merge.*failed|rebase.*failed": {
        "tool": "Bash",
        "suggestion": "Use smart-diff.sh to understand conflicts",
        "action": "use_diff"
    },
    r"timeout|timed out|killed": {
        "tool": "*",
        "suggestion": "Command too slow - try limiting scope or using more specific patterns",
        "action": "reduce_scope"
    },
}
ERROR_PATTERNS = [(re.compile(p, re.IGNORECASE), info) for p, info in _ERROR_PATTERNS_RAW.items()]

# Tool-specific alternative suggestions after repeated failures
TOOL_ALTERNATIVES = {
    "Grep": "Consider Task(subagent_type=Explore) for complex searches",
    "Glob": "Try smart-find.sh with fd for faster, .gitignore-aware search",
    "Read": "For large files, use smart-view.sh",
    "Edit": "If edits keep failing, re-read file or check for concurrent modifications",
    "Bash": "For build/test commands, pipe through compress-*.sh scripts",
}

def load_state(session_id: str) -> dict:
    """Load failure history state for session using centralized session state."""
    now = time.time()
    default = {"failures": {}, "last_update": now}
    state = read_session_state(STATE_NAMESPACE, session_id, default)
    if now - state.get("last_update", 0) > MAX_AGE_SECONDS:
        return default
    return state


def save_state(session_id: str, state: dict):
    """Save failure history state using centralized session state."""
    state["last_update"] = time.time()
    write_session_state(STATE_NAMESPACE, state, session_id)

def extract_error_info(tool_result) -> tuple[bool, str]:
    """Extract error status and message from tool result.

    Handles both dict and string tool_result formats.
    """
    # Handle string tool_result (direct output)
    if isinstance(tool_result, str):
        return False, tool_result[:500]

    # Handle non-dict types gracefully
    if not isinstance(tool_result, dict):
        return False, str(tool_result)[:500] if tool_result else ""

    # Check various error indicators
    is_error = tool_result.get("is_error", False)
    error_msg = ""

    content = tool_result.get("content", "")
    if isinstance(content, str):
        error_msg = content
    elif isinstance(content, list):
        for item in content:
            if isinstance(item, dict):
                text = item.get("text", "")
                if text:
                    error_msg += text + "\n"

    return is_error, error_msg[:500]  # Limit error message length

def match_error_pattern(error_msg: str) -> dict | None:
    """Match error message against pre-compiled patterns."""
    for compiled, info in ERROR_PATTERNS:
        if compiled.search(error_msg):
            return info
    return None

def track_success(ctx: dict) -> dict | None:
    """Handler function for dispatcher. Returns result dict or None."""
    tool_name = ctx.get("tool_name", "")
    # Claude Code uses "tool_response" for PostToolUse hooks
    tool_result = ctx.get("tool_response") or ctx.get("tool_result", {})
    session_id = get_session_id(ctx)

    if not tool_name:
        return None

    state = load_state(session_id)

    # Initialize failures dict for this tool if needed
    if tool_name not in state["failures"]:
        state["failures"][tool_name] = {
            "count": 0,
            "recent_errors": [],
            "last_success": time.time()
        }

    is_error, error_msg = extract_error_info(tool_result)
    messages = []

    if is_error or (error_msg and match_error_pattern(error_msg)):
        tool_failures = state["failures"][tool_name]
        tool_failures["count"] += 1
        tool_failures["recent_errors"].append({
            "msg": error_msg[:200],
            "time": time.time()
        })
        tool_failures["recent_errors"] = tool_failures["recent_errors"][-10:]

        # Check for specific error pattern
        pattern_match = match_error_pattern(error_msg)
        if pattern_match:
            messages.append(f"[Tool Tracker] {tool_name} error detected")
            messages.append(f"  Suggestion: {pattern_match['suggestion']}")
            log_event("tool_success_tracker", "error_pattern_matched", {"tool": tool_name, "action": pattern_match["action"]})

        # Check for repeated failures
        elif tool_failures["count"] >= FAILURE_THRESHOLD:
            messages.append(f"[Tool Tracker] {tool_name} has failed {tool_failures['count']} times this session")
            if tool_name in TOOL_ALTERNATIVES:
                messages.append(f"  Alternative: {TOOL_ALTERNATIVES[tool_name]}")
            log_event("tool_success_tracker", "repeated_failures", {"tool": tool_name, "count": tool_failures["count"]})

    else:
        # Success - reset failure count but keep history
        if tool_name in state["failures"]:
            state["failures"][tool_name]["count"] = 0
            state["failures"][tool_name]["last_success"] = time.time()

    save_state(session_id, state)

    if messages:
        return {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "message": "\n".join(messages)
            }
        }

    return None


@graceful_main("tool_success_tracker")
def main():
    try:
        ctx = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    result = track_success(ctx)
    if result:
        msg = result.get("hookSpecificOutput", {}).get("message", "")
        print(msg)

    sys.exit(0)


if __name__ == "__main__":
    main()

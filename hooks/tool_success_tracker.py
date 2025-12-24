#!/home/jonglaser/.claude/venv/bin/python3
"""
Tool Success Tracker Hook - Tracks tool failures and suggests alternatives.
Runs on PostToolUse to monitor errors and recommend better approaches.

Tracks failures in a session-specific temp file.
"""
import json
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
STATE_DIR = Path("/tmp/claude-tool-tracker")
MAX_AGE_SECONDS = 3600  # Clear state after 1 hour
FAILURE_THRESHOLD = 2  # Suggest alternative after 2 failures

# Error patterns and their suggested fixes
ERROR_PATTERNS = {
    # Edit failures
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
    # Permission errors
    r"permission denied|access denied|not permitted": {
        "tool": "*",
        "suggestion": "Check file permissions or try Task(subagent_type=Explore) for read-only exploration",
        "action": "check_perms"
    },
    # Grep/search failures
    r"no matches|no results|pattern not found": {
        "tool": "Grep",
        "suggestion": "Try broader pattern or use Task(subagent_type=Explore) for fuzzy search",
        "action": "broaden_search"
    },
    # Build failures
    r"build failed|compilation error|make.*error": {
        "tool": "Bash",
        "suggestion": "Pipe through compress-build.sh to focus on errors",
        "action": "compress_output"
    },
    # Test failures
    r"test.*failed|assertion.*error|pytest.*failed": {
        "tool": "Bash",
        "suggestion": "Pipe through compress-tests.sh to focus on failures",
        "action": "compress_output"
    },
    # Git errors
    r"conflict|merge.*failed|rebase.*failed": {
        "tool": "Bash",
        "suggestion": "Use smart-diff.sh to understand conflicts",
        "action": "use_diff"
    },
    # Timeout
    r"timeout|timed out|killed": {
        "tool": "*",
        "suggestion": "Command too slow - try limiting scope or using more specific patterns",
        "action": "reduce_scope"
    },
}

# Tool-specific alternative suggestions after repeated failures
TOOL_ALTERNATIVES = {
    "Grep": "Consider Task(subagent_type=Explore) for complex searches",
    "Glob": "Try smart-find.sh with fd for faster, .gitignore-aware search",
    "Read": "For large files, use smart-cat.sh with line ranges",
    "Edit": "If edits keep failing, re-read file or check for concurrent modifications",
    "Bash": "For build/test commands, pipe through compress-*.sh scripts",
}

def get_state_file(session_id: str) -> Path:
    """Get session-specific state file path."""
    STATE_DIR.mkdir(exist_ok=True)
    return STATE_DIR / f"failures_{session_id}.json"

def load_state(session_id: str) -> dict:
    """Load failure history state for session."""
    state_file = get_state_file(session_id)
    if state_file.exists():
        try:
            with open(state_file) as f:
                state = json.load(f)
                if time.time() - state.get("last_update", 0) > MAX_AGE_SECONDS:
                    return {"failures": {}, "last_update": time.time()}
                return state
        except (json.JSONDecodeError, IOError):
            pass
    return {"failures": {}, "last_update": time.time()}

def save_state(session_id: str, state: dict):
    """Save failure history state."""
    state["last_update"] = time.time()
    state_file = get_state_file(session_id)
    try:
        with open(state_file, "w") as f:
            json.dump(state, f)
    except IOError:
        pass

def extract_error_info(tool_result: dict) -> tuple[bool, str]:
    """Extract error status and message from tool result."""
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

    # Check for error patterns in content even if not marked as error
    if not is_error:
        error_indicators = ["error", "failed", "not found", "denied", "exception"]
        content_lower = error_msg.lower()
        if any(ind in content_lower for ind in error_indicators):
            # Could be an error even without is_error flag
            pass

    return is_error, error_msg[:500]  # Limit error message length

def match_error_pattern(error_msg: str) -> dict | None:
    """Match error message against known patterns."""
    error_lower = error_msg.lower()
    for pattern, info in ERROR_PATTERNS.items():
        if re.search(pattern, error_lower, re.IGNORECASE):
            return info
    return None

@graceful_main("tool_success_tracker")
def main():
    try:
        ctx = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = ctx.get("tool_name", "")
    tool_result = ctx.get("tool_result", {})
    session_id = ctx.get("session_id", "default")

    if not tool_name:
        sys.exit(0)

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
        # Keep only last 10 errors
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
        print("\n".join(messages))

    sys.exit(0)

if __name__ == "__main__":
    main()

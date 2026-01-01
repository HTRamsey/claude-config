#!/home/jonglaser/.claude/data/venv/bin/python3
"""
Tool Analytics - Unified tool tracking, output metrics, and failure detection.

Consolidates:
- tool_success_tracker: Track tool failures and suggest alternatives
- output_metrics: Token tracking and output size monitoring

Both share token estimation logic and PostToolUse context processing.
"""
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

from hook_utils import (
    graceful_main,
    log_event,
    safe_load_json,
    safe_save_json,
    get_session_id,
    read_session_state,
    write_session_state,
)
from config import Thresholds, FilePatterns, Timeouts, TRACKER_DIR

# =============================================================================
# Shared Configuration
# =============================================================================

CHARS_PER_TOKEN = Thresholds.CHARS_PER_TOKEN
OUTPUT_WARNING_THRESHOLD = Thresholds.OUTPUT_WARNING
OUTPUT_CRITICAL_THRESHOLD = Thresholds.OUTPUT_CRITICAL
DAILY_WARNING_THRESHOLD = Thresholds.DAILY_TOKEN_WARNING
LARGE_OUTPUT_TOOLS = FilePatterns.LARGE_OUTPUT_TOOLS
FAILURE_THRESHOLD = Thresholds.TOOL_FAILURE_THRESHOLD
TOOL_TRACKER_MAX_AGE = Timeouts.TOOL_TRACKER_MAX_AGE
STATE_NAMESPACE = "tool_tracker"

# =============================================================================
# Shared Utilities
# =============================================================================

def estimate_tokens(content) -> int:
    """Estimate tokens from content."""
    if isinstance(content, str):
        return len(content) // CHARS_PER_TOKEN
    elif isinstance(content, dict):
        return len(json.dumps(content)) // CHARS_PER_TOKEN
    elif isinstance(content, list):
        return sum(estimate_tokens(item) for item in content)
    return 0


def get_content_size(content) -> int:
    """Get size of content in characters."""
    if isinstance(content, str):
        return len(content)
    elif isinstance(content, dict):
        return len(json.dumps(content))
    elif isinstance(content, list):
        return sum(get_content_size(item) for item in content)
    return 0


# =============================================================================
# Tool Success Tracker
# =============================================================================

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

TOOL_ALTERNATIVES = {
    "Grep": "Consider Task(subagent_type=Explore) for complex searches",
    "Glob": "Try smart-find.sh with fd for faster, .gitignore-aware search",
    "Read": "For large files, use smart-view.sh",
    "Edit": "If edits keep failing, re-read file or check for concurrent modifications",
    "Bash": "For build/test commands, pipe through compress-*.sh scripts",
}


def load_tracker_state(session_id: str) -> dict:
    """Load failure history state for session."""
    now = time.time()
    default = {"failures": {}, "last_update": now}
    state = read_session_state(STATE_NAMESPACE, session_id, default)
    if now - state.get("last_update", 0) > TOOL_TRACKER_MAX_AGE:
        return default
    return state


def save_tracker_state(session_id: str, state: dict):
    """Save failure history state."""
    state["last_update"] = time.time()
    write_session_state(STATE_NAMESPACE, state, session_id)


def extract_error_info(tool_result) -> tuple[bool, str]:
    """Extract error status and message from tool result."""
    if isinstance(tool_result, str):
        return False, tool_result[:500]
    if not isinstance(tool_result, dict):
        return False, str(tool_result)[:500] if tool_result else ""

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

    return is_error, error_msg[:500]


def match_error_pattern(error_msg: str) -> dict | None:
    """Match error message against pre-compiled patterns."""
    for compiled, info in ERROR_PATTERNS:
        if compiled.search(error_msg):
            return info
    return None


def track_success(ctx: dict) -> list[str]:
    """Track tool success/failure. Returns list of messages."""
    tool_name = ctx.get("tool_name", "")
    tool_result = ctx.get("tool_response") or ctx.get("tool_result", {})
    session_id = get_session_id(ctx)

    if not tool_name:
        return []

    state = load_tracker_state(session_id)

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

        pattern_match = match_error_pattern(error_msg)
        if pattern_match:
            messages.append(f"[Tool Tracker] {tool_name} error detected")
            messages.append(f"  Suggestion: {pattern_match['suggestion']}")
            log_event("tool_analytics", "error_pattern_matched", {"tool": tool_name, "action": pattern_match["action"]})
        elif tool_failures["count"] >= FAILURE_THRESHOLD:
            messages.append(f"[Tool Tracker] {tool_name} has failed {tool_failures['count']} times this session")
            if tool_name in TOOL_ALTERNATIVES:
                messages.append(f"  Alternative: {TOOL_ALTERNATIVES[tool_name]}")
            log_event("tool_analytics", "repeated_failures", {"tool": tool_name, "count": tool_failures["count"]})
    else:
        if tool_name in state["failures"]:
            state["failures"][tool_name]["count"] = 0
            state["failures"][tool_name]["last_success"] = time.time()

    save_tracker_state(session_id, state)
    return messages


# =============================================================================
# Token Tracker & Output Size Monitor
# =============================================================================

# Use TTLCache with 5-minute TTL (cache invalidates on date change check anyway)
from cachetools import TTLCache
_daily_stats_cache: TTLCache = TTLCache(maxsize=1, ttl=300)
_DAILY_STATS_KEY = "daily_stats"
_STATS_FLUSH_INTERVAL = 10


def get_daily_log_path() -> Path:
    """Get path to today's token log."""
    today = datetime.now().strftime("%Y-%m-%d")
    return TRACKER_DIR / f"tokens-{today}.json"


def load_daily_stats() -> dict:
    """Load today's statistics with caching."""
    today = datetime.now().strftime("%Y-%m-%d")

    # Check cache - but invalidate if date changed
    if _DAILY_STATS_KEY in _daily_stats_cache:
        cached = _daily_stats_cache[_DAILY_STATS_KEY]
        if cached.get("date") == today:
            return cached

    log_path = get_daily_log_path()
    default = {
        "date": today,
        "total_tokens": 0,
        "tool_calls": 0,
        "by_tool": {},
        "sessions": 0,
    }
    data = safe_load_json(log_path, default)

    _daily_stats_cache[_DAILY_STATS_KEY] = data
    return data


def save_daily_stats(stats: dict, force: bool = False):
    """Save today's statistics with batching."""
    _daily_stats_cache[_DAILY_STATS_KEY] = stats

    if force or stats.get("tool_calls", 0) % _STATS_FLUSH_INTERVAL == 0:
        TRACKER_DIR.mkdir(parents=True, exist_ok=True)
        log_path = get_daily_log_path()
        safe_save_json(log_path, stats)


def track_tokens(ctx: dict) -> list[str]:
    """Track token usage. Returns list of messages if warning threshold reached."""
    tool_name = ctx.get("tool_name", "unknown")
    tool_input = ctx.get("tool_input", {})
    tool_result = ctx.get("tool_response") or ctx.get("tool_result", {})

    input_tokens = estimate_tokens(tool_input)
    output_tokens = estimate_tokens(tool_result)
    total_tokens = input_tokens + output_tokens

    stats = load_daily_stats()
    stats["total_tokens"] += total_tokens
    stats["tool_calls"] += 1
    stats["by_tool"][tool_name] = stats["by_tool"].get(tool_name, 0) + total_tokens
    save_daily_stats(stats)

    messages = []
    if stats["total_tokens"] >= DAILY_WARNING_THRESHOLD:
        if stats["tool_calls"] % 50 == 0:
            messages.append(f"[Token Tracker] Daily usage: ~{stats['total_tokens']:,} tokens")
            top_tools = sorted(stats["by_tool"].items(), key=lambda x: -x[1])[:3]
            if top_tools:
                tools_str = ", ".join(f"{t}: {c:,}" for t, c in top_tools)
                messages.append(f"  Top tools: {tools_str}")

    return messages


def check_output_size(ctx: dict) -> list[str]:
    """Check output size. Returns list of messages if too large."""
    tool_name = ctx.get("tool_name", "")
    tool_result = ctx.get("tool_response") or ctx.get("tool_result", {})

    output_size = get_content_size(tool_result)
    if output_size == 0:
        return []

    estimated_tokens = estimate_tokens(tool_result)

    warning_threshold = OUTPUT_WARNING_THRESHOLD
    critical_threshold = OUTPUT_CRITICAL_THRESHOLD
    if tool_name in LARGE_OUTPUT_TOOLS:
        warning_threshold *= 3
        critical_threshold *= 3

    messages = []

    if output_size >= critical_threshold:
        messages.append(f"[Output Monitor] Large output from {tool_name}: ~{estimated_tokens:,} tokens ({output_size:,} chars)")
        messages.append("  Consider using compression scripts or limiting output.")
        if tool_name == "Bash":
            messages.append("  Tip: Pipe to head, use compress-*.sh scripts, or add output limits")
        elif tool_name == "Grep":
            messages.append("  Tip: Use head_limit parameter or offload-grep.sh")
        elif tool_name == "Read":
            messages.append("  Tip: Use smart-view.sh for large files")
    elif output_size >= warning_threshold:
        messages.append(f"[Output Monitor] {tool_name} output: ~{estimated_tokens:,} tokens")

    return messages


# =============================================================================
# Combined Handler
# =============================================================================

def track_tool_analytics(ctx: dict) -> dict | None:
    """Combined handler for tool success tracking, token tracking, and output monitoring."""
    all_messages = []

    # Track tool success/failure
    success_messages = track_success(ctx)
    all_messages.extend(success_messages)

    # Track tokens (always runs, updates stats)
    token_messages = track_tokens(ctx)
    all_messages.extend(token_messages)

    # Check output size
    size_messages = check_output_size(ctx)
    all_messages.extend(size_messages)

    if all_messages:
        return {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "message": " | ".join(all_messages[:3])  # Limit to 3 messages
            }
        }

    return None


# =============================================================================
# Main
# =============================================================================

@graceful_main("tool_analytics")
def main():
    try:
        ctx = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    result = track_tool_analytics(ctx)
    if result:
        msg = result.get("hookSpecificOutput", {}).get("message", "")
        if msg:
            print(msg)

    sys.exit(0)


if __name__ == "__main__":
    main()

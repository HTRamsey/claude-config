#!/home/jonglaser/.claude/venv/bin/python3
"""
Output Metrics - Unified token tracking and output size monitoring.

Consolidates:
- token_tracker: Track daily token usage with persistence
- output_size_monitor: Warn about large outputs

Both share token estimation logic and PostToolUse context processing.
"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from hook_utils import graceful_main, log_event, safe_load_json, safe_save_json

# ============================================================================
# Shared Configuration
# ============================================================================

CHARS_PER_TOKEN = 4
DATA_DIR = Path.home() / ".claude/data"
TRACKER_DIR = Path(os.environ.get("CLAUDE_TRACKER_DIR", Path.home() / ".claude/tracking"))

# Output size thresholds
OUTPUT_WARNING_THRESHOLD = 10000  # Warn if output > 10K chars
OUTPUT_CRITICAL_THRESHOLD = 50000  # Strong warning if > 50K chars

# Token tracking thresholds
DAILY_WARNING_THRESHOLD = 500000  # Warn at 500K tokens/day

# Tools with expected large output (less aggressive warnings)
LARGE_OUTPUT_TOOLS = ["Task", "WebFetch", "WebSearch"]

# ============================================================================
# Shared Utilities
# ============================================================================

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

# ============================================================================
# Token Tracker
# ============================================================================

def get_daily_log_path() -> Path:
    """Get path to today's token log."""
    today = datetime.now().strftime("%Y-%m-%d")
    return TRACKER_DIR / f"tokens-{today}.json"

def load_daily_stats() -> dict:
    """Load today's statistics."""
    log_path = get_daily_log_path()
    default = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "total_tokens": 0,
        "tool_calls": 0,
        "by_tool": {},
        "sessions": 0,
    }
    return safe_load_json(log_path, default)

def save_daily_stats(stats: dict):
    """Save today's statistics."""
    TRACKER_DIR.mkdir(parents=True, exist_ok=True)
    log_path = get_daily_log_path()
    safe_save_json(log_path, stats)

def track_tokens(ctx: dict) -> dict | None:
    """Track token usage and warn if approaching daily limit."""
    tool_name = ctx.get("tool_name", "unknown")
    tool_input = ctx.get("tool_input", {})
    tool_result = ctx.get("tool_result", {})

    input_tokens = estimate_tokens(tool_input)
    output_tokens = estimate_tokens(tool_result)
    total_tokens = input_tokens + output_tokens

    stats = load_daily_stats()
    stats["total_tokens"] += total_tokens
    stats["tool_calls"] += 1
    stats["by_tool"][tool_name] = stats["by_tool"].get(tool_name, 0) + total_tokens
    save_daily_stats(stats)

    if stats["total_tokens"] >= DAILY_WARNING_THRESHOLD:
        if stats["tool_calls"] % 50 == 0:
            messages = [f"[Token Tracker] Daily usage: ~{stats['total_tokens']:,} tokens"]
            top_tools = sorted(stats["by_tool"].items(), key=lambda x: -x[1])[:3]
            if top_tools:
                tools_str = ", ".join(f"{t}: {c:,}" for t, c in top_tools)
                messages.append(f"  Top tools: {tools_str}")
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "message": "\n".join(messages)
                }
            }

    return None

# ============================================================================
# Output Size Monitor
# ============================================================================

def check_output_size(ctx: dict) -> dict | None:
    """Check output size and warn if too large."""
    tool_name = ctx.get("tool_name", "")
    tool_result = ctx.get("tool_result", {})

    output_size = get_content_size(tool_result)
    if output_size == 0:
        return None

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

    if messages:
        return {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "message": "\n".join(messages)
            }
        }

    return None

# ============================================================================
# Combined Handler
# ============================================================================

def track_output_metrics(ctx: dict) -> dict | None:
    """Combined handler for both token tracking and output size monitoring."""
    messages = []

    # Track tokens (always runs, updates stats)
    token_result = track_tokens(ctx)
    if token_result:
        msg = token_result.get("hookSpecificOutput", {}).get("message", "")
        if msg:
            messages.append(msg)

    # Check output size
    size_result = check_output_size(ctx)
    if size_result:
        msg = size_result.get("hookSpecificOutput", {}).get("message", "")
        if msg:
            messages.append(msg)

    if messages:
        return {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "message": " | ".join(messages)
            }
        }

    return None

# ============================================================================
# Main
# ============================================================================

@graceful_main("output_metrics")
def main():
    try:
        ctx = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    result = track_output_metrics(ctx)
    if result:
        msg = result.get("hookSpecificOutput", {}).get("message", "")
        if msg:
            print(msg)

    sys.exit(0)


if __name__ == "__main__":
    main()

#!/home/jonglaser/.claude/venv/bin/python3
"""Track token usage across sessions for cost awareness.

PostToolUse hook that tracks estimated token consumption.
Saves daily totals to a log file for analysis.
"""
import json
import os
import sys
from datetime import datetime
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
TRACKER_DIR = Path(os.environ.get("CLAUDE_TRACKER_DIR", Path.home() / ".claude" / "tracking"))
CHARS_PER_TOKEN = 4  # Rough estimate
DAILY_WARNING_THRESHOLD = 500000  # Warn at 500K tokens/day

def ensure_tracker_dir():
    """Ensure tracking directory exists"""
    TRACKER_DIR.mkdir(parents=True, exist_ok=True)

def get_daily_log_path() -> Path:
    """Get path to today's token log"""
    today = datetime.now().strftime("%Y-%m-%d")
    return TRACKER_DIR / f"tokens-{today}.json"

def load_daily_stats() -> dict:
    """Load today's statistics"""
    log_path = get_daily_log_path()
    if log_path.exists():
        try:
            with open(log_path) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "total_tokens": 0,
        "tool_calls": 0,
        "by_tool": {},
        "sessions": 0,
    }

def save_daily_stats(stats: dict):
    """Save today's statistics"""
    ensure_tracker_dir()
    log_path = get_daily_log_path()
    try:
        with open(log_path, 'w') as f:
            json.dump(stats, f, indent=2)
    except IOError:
        pass

def estimate_tokens(text) -> int:
    """Estimate tokens from text"""
    if isinstance(text, str):
        return len(text) // CHARS_PER_TOKEN
    elif isinstance(text, dict):
        return estimate_tokens(json.dumps(text))
    elif isinstance(text, list):
        return sum(estimate_tokens(item) for item in text)
    return 0


def track_tokens(ctx: dict) -> dict | None:
    """Handler function for dispatcher. Returns result dict or None."""
    tool_name = ctx.get("tool_name", "unknown")
    tool_input = ctx.get("tool_input", {})
    tool_result = ctx.get("tool_result", {})

    # Estimate tokens for this call
    input_tokens = estimate_tokens(tool_input)
    output_tokens = estimate_tokens(tool_result)
    total_tokens = input_tokens + output_tokens

    # Load and update daily stats
    stats = load_daily_stats()
    stats["total_tokens"] += total_tokens
    stats["tool_calls"] += 1
    stats["by_tool"][tool_name] = stats["by_tool"].get(tool_name, 0) + total_tokens

    # Save updated stats
    save_daily_stats(stats)

    # Warn if approaching daily threshold
    if stats["total_tokens"] >= DAILY_WARNING_THRESHOLD:
        if stats["tool_calls"] % 50 == 0:  # Don't spam, warn every 50 calls
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


@graceful_main("token_tracker")
def main():
    try:
        ctx = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    result = track_tokens(ctx)
    if result:
        msg = result.get("hookSpecificOutput", {}).get("message", "")
        print(msg)

    sys.exit(0)


if __name__ == "__main__":
    main()

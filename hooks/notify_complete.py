#!/home/jonglaser/.claude/data/venv/bin/python3
"""
Notification Hook - Alert when long Bash operations complete.
PostToolUse hook for Bash tool.

Sends desktop notification if command took > 30 seconds.
"""
import json
import subprocess
import sys
from pathlib import Path

# Import shared utilities
sys.path.insert(0, str(Path(__file__).parent))
from hook_utils import graceful_main, log_event

# Minimum duration (seconds) to trigger notification
MIN_DURATION_SECS = 30

def send_notification(title: str, message: str, urgency: str = "normal"):
    """Send desktop notification using notify-send (Linux)"""
    try:
        subprocess.run([
            "notify-send",
            "--urgency", urgency,
            "--app-name", "Claude Code",
            "--icon", "terminal",
            title,
            message
        ], timeout=5, capture_output=True)
    except Exception:
        pass  # Silently fail if notify-send not available

def check_notify(ctx: dict) -> dict | None:
    """Handler function for dispatcher. Returns result dict or None."""
    tool_name = ctx.get("tool_name", "")

    # Only process Bash tool completions
    if tool_name != "Bash":
        return None

    # Get duration if available
    duration_ms = ctx.get("duration_ms", 0)
    duration_secs = duration_ms / 1000

    if duration_secs < MIN_DURATION_SECS:
        return None

    # Get command info
    tool_input = ctx.get("tool_input", {})
    command = tool_input.get("command", "")[:50]  # Truncate

    # Check if it succeeded or failed (Claude Code uses "tool_response")
    tool_result = ctx.get("tool_response") or ctx.get("tool_result", {})
    # Check both exit_code and exitCode variants
    exit_code = tool_result.get("exit_code")
    if exit_code is None:
        exit_code = tool_result.get("exitCode", 0)

    if exit_code == 0:
        title = "✓ Command Complete"
        urgency = "normal"
    else:
        title = "✗ Command Failed"
        urgency = "critical"

    message = f"{command}...\nDuration: {duration_secs:.0f}s"

    send_notification(title, message, urgency)
    log_event("notify_complete", "notification_sent", {"duration": duration_secs, "success": exit_code == 0})

    return None  # Notification sent, no message to return


@graceful_main("notify_complete")
def main():
    try:
        ctx = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    check_notify(ctx)
    sys.exit(0)


if __name__ == "__main__":
    main()

"""
Desktop notification for long-running commands.

PostToolUse handler for Bash tool - sends desktop notification
when commands take >30 seconds to complete.
"""
import shutil
import subprocess

from hooks.config import Thresholds


def notify_complete(raw: dict) -> dict | None:
    """Send desktop notification for long Bash commands."""
    tool_name = raw.get("tool_name", "")
    if tool_name != "Bash":
        return None

    duration_ms = raw.get("duration_ms", 0)
    duration_secs = duration_ms // 1000

    if duration_secs < Thresholds.min_notify_duration:
        return None

    # Check if notify-send is available
    if not shutil.which("notify-send"):
        return None

    # Extract command and exit code
    tool_input = raw.get("tool_input", {})
    command = (tool_input.get("command") or "")[:50]

    tool_response = raw.get("tool_response") or raw.get("tool_result") or {}
    exit_code = tool_response.get("exit_code", 0)

    # Determine notification type
    if exit_code == 0:
        title = "✓ Command Complete"
        urgency = "normal"
    else:
        title = "✗ Command Failed"
        urgency = "critical"

    message = f"{command}...\nDuration: {duration_secs}s"

    # Send notification asynchronously (don't block dispatcher)
    subprocess.Popen(
        [
            "notify-send",
            "--urgency", urgency,
            "--app-name", "Claude Code",
            "--icon", "terminal",
            title,
            message,
        ],
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    return None

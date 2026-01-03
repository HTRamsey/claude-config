"""
Git context handler - check for uncommitted changes and handle stop events.

Provides git status checks for stop dispatcher and other events.
"""
import json
import os

from hooks.hook_utils import git
from hooks.handlers import auto_continue


def check_uncommitted_changes(ctx: dict) -> list[str]:
    """Check for uncommitted git changes. Returns list of messages."""
    cwd = ctx.get("cwd") or ctx.get("working_directory") or os.getcwd()
    status = git.get_status(cwd)

    if not status["is_git_repo"]:
        return []

    messages = []

    if status["has_staged"] or status["has_unstaged"]:
        msg_parts = []
        if status["has_staged"]:
            msg_parts.append("staged")
        if status["has_unstaged"]:
            msg_parts.append("unstaged")
        messages.append(f"Uncommitted changes ({', '.join(msg_parts)}) in {status['file_count']} files")

    if status["ahead"] > 0:
        messages.append(f"Branch '{status['branch']}' is {status['ahead']} commits ahead of remote (unpushed)")

    if status["has_untracked"] and status["file_count"] <= 10:
        messages.append("Untracked files present")

    return messages


def format_stop_output(messages: list[str], continue_result: dict | None) -> list[str]:
    """Format stop event output with uncommitted changes and continue result.

    Args:
        messages: List of uncommitted change messages
        continue_result: Auto-continue result dict or None

    Returns:
        List of formatted output lines
    """
    output_parts = []

    # Format uncommitted change warnings
    if messages:
        output_parts.append("[Uncommitted Changes] Before ending session:")
        for msg in messages:
            output_parts.append(f"  - {msg}")
        if any("Uncommitted" in m for m in messages):
            output_parts.append("  Consider: git commit -m 'WIP: <description>'")
        if any("ahead" in m for m in messages):
            output_parts.append("  Consider: git push")

    # Add continue result as JSON
    if continue_result:
        output_parts.append(json.dumps(continue_result))

    return output_parts


def handle_stop(ctx: dict) -> list[str]:
    """Unified Stop handler - checks git status and auto-continue.

    Args:
        ctx: Context with 'cwd' or 'working_directory' key

    Returns:
        List of formatted output lines
    """
    uncommitted_messages = check_uncommitted_changes(ctx)
    continue_result = auto_continue.check_auto_continue(ctx)
    return format_stop_output(uncommitted_messages, continue_result)

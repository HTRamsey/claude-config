#!/home/jonglaser/.claude/data/venv/bin/python3
"""
Stop Dispatcher - Consolidated Stop hooks.

Handlers (now in handlers/):
- git_context: Check for uncommitted git changes
- auto_continue: Evaluate if Claude should continue working

Runs on Stop event to handle session ending.
"""
import json
import os

from hooks.dispatchers.base import SimpleDispatcher
from hooks.handlers import git_context, auto_continue


def check_uncommitted_changes(ctx: dict) -> list[str]:
    """Check for uncommitted git changes. Returns list of messages."""
    cwd = ctx.get("cwd") or ctx.get("working_directory") or os.getcwd()
    status = git_context.get_status(cwd)

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


def handle_stop(ctx: dict) -> tuple[list[str], dict | None]:
    """Handle Stop event.

    Returns:
        (messages, continue_result)
        - messages: List of warning messages to display
        - continue_result: Dict with "result": "continue" if should continue, else None
    """
    uncommitted_messages = check_uncommitted_changes(ctx)
    continue_result = auto_continue.check_auto_continue(ctx)
    return uncommitted_messages, continue_result


class StopDispatcher(SimpleDispatcher):
    """Stop event dispatcher with special output handling."""

    DISPATCHER_NAME = "stop_handler"
    EVENT_TYPE = "Stop"

    def __init__(self):
        super().__init__()
        self._continue_result = None

    def handle(self, ctx: dict) -> list[str]:
        messages, continue_result = handle_stop(ctx)
        self._continue_result = continue_result
        return messages

    def format_output(self, messages: list[str]) -> str | None:
        """Custom formatting for uncommitted changes + continue result."""
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
        if self._continue_result:
            output_parts.append(json.dumps(self._continue_result))

        return "\n".join(output_parts) if output_parts else None


if __name__ == "__main__":
    StopDispatcher().run()

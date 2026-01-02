#!/home/jonglaser/.claude/data/venv/bin/python3
"""
PostToolUseFailure Dispatcher - Handle tool execution failures.

Tracks tool failures for analytics and debugging.
Can provide context-aware failure messages.

Runs on PostToolUseFailure event when any tool fails.
"""
from hooks.dispatchers.base import SimpleDispatcher
from hooks.hook_utils import log_event


def handle_tool_failure(ctx: dict) -> list[str]:
    """Handle PostToolUseFailure event.

    Args:
        ctx: Context with tool_name, tool_input, error, exit_code (for Bash)

    Returns:
        List of messages (usually empty - logging only)
    """
    tool_name = ctx.get("tool_name", "unknown")
    error = ctx.get("error", "")
    tool_input = ctx.get("tool_input", {})

    # Extract relevant info based on tool type
    details = {"tool": tool_name, "error": error[:200]}

    if tool_name == "Bash":
        details["command"] = (tool_input.get("command") or "")[:100]
        details["exit_code"] = ctx.get("exit_code")
    elif tool_name == "Read":
        details["file_path"] = tool_input.get("file_path", "")
    elif tool_name == "Edit":
        details["file_path"] = tool_input.get("file_path", "")
        details["old_string_len"] = len(tool_input.get("old_string", ""))
    elif tool_name == "Write":
        details["file_path"] = tool_input.get("file_path", "")
    elif tool_name == "Task":
        details["subagent_type"] = tool_input.get("subagent_type", "")
    elif tool_name == "Grep":
        details["pattern"] = tool_input.get("pattern", "")
    elif tool_name == "Glob":
        details["pattern"] = tool_input.get("pattern", "")

    log_event("tool_failure", tool_name, details)

    # No user-facing messages by default
    # The tool failure is already visible to the user
    return []


class PostToolFailureDispatcher(SimpleDispatcher):
    """PostToolUseFailure event dispatcher."""

    DISPATCHER_NAME = "post_tool_failure_handler"
    EVENT_TYPE = "PostToolUseFailure"

    def handle(self, ctx: dict) -> list[str]:
        return handle_tool_failure(ctx)


if __name__ == "__main__":
    PostToolFailureDispatcher().run()

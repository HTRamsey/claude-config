#!/home/jonglaser/.claude/data/venv/bin/python3
"""
PostToolUseFailure Dispatcher - Handle tool execution failures.

Delegates to handlers/tool_failure.py for:
- Tool-specific detail extraction
- Failure logging for analytics

Runs on PostToolUseFailure event when any tool fails.
"""
from hooks.dispatchers.base import SimpleDispatcher
from hooks.handlers.tool_failure import handle_tool_failure


class PostToolFailureDispatcher(SimpleDispatcher):
    """PostToolUseFailure event dispatcher."""

    DISPATCHER_NAME = "post_tool_failure_handler"
    EVENT_TYPE = "PostToolUseFailure"

    def handle(self, ctx: dict) -> list[str]:
        return handle_tool_failure(ctx)


if __name__ == "__main__":
    PostToolFailureDispatcher().run()

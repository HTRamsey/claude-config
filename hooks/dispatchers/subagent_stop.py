#!/home/jonglaser/.claude/data/venv/bin/python3
"""
SubagentStop Dispatcher - Handle subagent completion events.

Handlers (in handlers/):
- subagent_lifecycle: Track completion timing, reflexion memory

Runs on SubagentStop event when Task tool subagents finish.
"""
from hooks.dispatchers.base import SimpleDispatcher
from hooks.handlers import subagent_lifecycle
from hooks.hook_utils import log_event


def handle_subagent_stop(ctx: dict) -> list[str]:
    """Handle SubagentStop event.

    Args:
        ctx: Context with subagent_id, subagent_type, stop_reason, output

    Returns:
        List of messages (usually empty - logging only)
    """
    subagent_type = ctx.get("subagent_type", "unknown")
    subagent_id = ctx.get("subagent_id", "")
    stop_reason = ctx.get("stop_reason", "completed")

    # Delegate to lifecycle handler for metrics and reflexion
    raw = {
        "tool_name": "Task",
        "tool_input": {
            "subagent_type": subagent_type,
        },
        "subagent_id": subagent_id,
        "stop_reason": stop_reason,
        "tool_output": ctx.get("output", ""),
    }
    subagent_lifecycle.handle_complete(raw)

    log_event("subagent_stop", "handled", {
        "subagent_type": subagent_type,
        "subagent_id": subagent_id,
        "stop_reason": stop_reason,
    })

    # No user-facing messages by default
    return []


class SubagentStopDispatcher(SimpleDispatcher):
    """SubagentStop event dispatcher."""

    DISPATCHER_NAME = "subagent_stop_handler"
    EVENT_TYPE = "SubagentStop"

    def handle(self, ctx: dict) -> list[str]:
        return handle_subagent_stop(ctx)


if __name__ == "__main__":
    SubagentStopDispatcher().run()

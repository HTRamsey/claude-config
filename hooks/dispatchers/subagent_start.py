#!/home/jonglaser/.claude/data/venv/bin/python3
"""
SubagentStart Dispatcher - Handle subagent spawn events.

Handlers (in handlers/):
- subagent_lifecycle: Track spawn timing, usage stats

Runs on SubagentStart event when Task tool subagents are created.
"""
from hooks.dispatchers.base import SimpleDispatcher
from hooks.handlers import subagent_lifecycle
from hooks.hook_utils import log_event


def handle_subagent_start(ctx: dict) -> list[str]:
    """Handle SubagentStart event.

    Args:
        ctx: Context with subagent_id, subagent_type, description, prompt

    Returns:
        List of messages (usually empty - logging only)
    """
    subagent_type = ctx.get("subagent_type", "unknown")
    subagent_id = ctx.get("subagent_id", "")
    description = ctx.get("description", "")
    prompt = ctx.get("prompt", "")

    # Delegate to lifecycle handler for metrics and usage tracking
    raw = {
        "tool_name": "Task",
        "tool_input": {
            "subagent_type": subagent_type,
            "description": description,
            "prompt": prompt,
        },
        "subagent_id": subagent_id,
    }
    subagent_lifecycle.handle_start(raw)

    log_event("subagent_start", "dispatched", {
        "subagent_type": subagent_type,
        "subagent_id": subagent_id,
        "has_description": bool(description),
    })

    # No user-facing messages by default
    return []


class SubagentStartDispatcher(SimpleDispatcher):
    """SubagentStart event dispatcher."""

    DISPATCHER_NAME = "subagent_start_handler"
    EVENT_TYPE = "SubagentStart"

    def handle(self, ctx: dict) -> list[str]:
        return handle_subagent_start(ctx)


if __name__ == "__main__":
    SubagentStartDispatcher().run()

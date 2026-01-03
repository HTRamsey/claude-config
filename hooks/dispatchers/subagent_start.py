#!/home/jonglaser/.claude/data/venv/bin/python3
"""
SubagentStart Dispatcher - Handle subagent spawn events.

Delegates to handlers/subagent_lifecycle.py for:
- Tracking spawn timing and usage stats

Runs on SubagentStart event when Task tool subagents are created.
"""
from hooks.dispatchers.base import SimpleDispatcher
from hooks.handlers.subagent_lifecycle import handle_subagent_start_event


class SubagentStartDispatcher(SimpleDispatcher):
    """SubagentStart event dispatcher."""

    DISPATCHER_NAME = "subagent_start_handler"
    EVENT_TYPE = "SubagentStart"

    def handle(self, ctx: dict) -> list[str]:
        return handle_subagent_start_event(ctx)


if __name__ == "__main__":
    SubagentStartDispatcher().run()

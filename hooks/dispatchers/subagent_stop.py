#!/home/jonglaser/.claude/data/venv/bin/python3
"""
SubagentStop Dispatcher - Handle subagent completion events.

Delegates to handlers/subagent_lifecycle.py for:
- Tracking completion timing and reflexion memory

Runs on SubagentStop event when Task tool subagents finish.
"""
from hooks.dispatchers.base import SimpleDispatcher
from hooks.handlers.subagent_lifecycle import handle_subagent_stop_event


class SubagentStopDispatcher(SimpleDispatcher):
    """SubagentStop event dispatcher."""

    DISPATCHER_NAME = "subagent_stop_handler"
    EVENT_TYPE = "SubagentStop"

    def handle(self, ctx: dict) -> list[str]:
        return handle_subagent_stop_event(ctx)


if __name__ == "__main__":
    SubagentStopDispatcher().run()

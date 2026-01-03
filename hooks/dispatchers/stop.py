#!/home/jonglaser/.claude/data/venv/bin/python3
"""
Stop Dispatcher - Handle stop events.

Delegates to handlers/git_context.py for:
- Uncommitted git changes check
- Auto-continue evaluation
- Output formatting

Runs on Stop event when session is ending.
"""
from hooks.dispatchers.base import SimpleDispatcher
from hooks.handlers.git_context import handle_stop


class StopDispatcher(SimpleDispatcher):
    """Stop event dispatcher."""

    DISPATCHER_NAME = "stop_handler"
    EVENT_TYPE = "Stop"

    def handle(self, ctx: dict) -> list[str]:
        return handle_stop(ctx)


if __name__ == "__main__":
    StopDispatcher().run()

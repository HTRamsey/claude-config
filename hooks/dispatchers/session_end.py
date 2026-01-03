#!/home/jonglaser/.claude/data/venv/bin/python3
"""
SessionEnd Dispatcher - Handle session end events.

Delegates to handlers/session_persistence.py for:
- Cleanup of old session files
- Transcript info extraction
- Session metadata saving
- Memory MCP suggestions
- Transcript conversion
- Usage cache update

Runs on SessionEnd event when a session is ending.
"""
from hooks.dispatchers.base import SimpleDispatcher
from hooks.handlers.session_persistence import handle_session_end


class SessionEndDispatcher(SimpleDispatcher):
    """SessionEnd event dispatcher."""

    DISPATCHER_NAME = "session_end_handler"
    EVENT_TYPE = None  # SessionEnd doesn't have event_type in context

    def handle(self, ctx: dict) -> list[str]:
        return handle_session_end(ctx)


if __name__ == "__main__":
    SessionEndDispatcher().run()

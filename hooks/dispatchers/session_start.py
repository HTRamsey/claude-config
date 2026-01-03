#!/home/jonglaser/.claude/data/venv/bin/python3
"""
SessionStart Dispatcher - Handle session start events.

Delegates to handlers/project_context.py for:
- Git context (branch, commits, status)
- Usage summary (sessions, agents, skills)
- Project type detection
- Viewer daemon startup

Runs on SessionStart event when a new session begins.
"""
from hooks.dispatchers.base import SimpleDispatcher
from hooks.handlers.project_context import handle_session_start


class SessionStartDispatcher(SimpleDispatcher):
    """SessionStart event dispatcher."""

    DISPATCHER_NAME = "session_start_dispatcher"
    EVENT_TYPE = None  # SessionStart doesn't have event_type in context

    def handle(self, ctx: dict) -> list[str]:
        return handle_session_start(ctx)


if __name__ == "__main__":
    SessionStartDispatcher().run()

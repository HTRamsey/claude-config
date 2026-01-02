#!/home/jonglaser/.claude/data/venv/bin/python3
"""
SessionStart Dispatcher - Consolidates all SessionStart hooks.

Uses:
- hook_utils/git: Git branch, commits, status
- handlers/project_context: Project type, usage stats
- handlers/viewer: Launch claude-code-viewer if not running
"""
import os

from hooks.dispatchers.base import SimpleDispatcher
from hooks.handlers import project_context
from hooks.hook_utils import git
from hooks.handlers.viewer import maybe_start_viewer


class SessionStartDispatcher(SimpleDispatcher):
    """SessionStart event dispatcher."""

    DISPATCHER_NAME = "session_start_dispatcher"
    EVENT_TYPE = None  # SessionStart doesn't have event_type in context

    def handle(self, ctx: dict) -> list[str]:
        cwd = ctx.get('cwd', os.getcwd())
        output_parts = ["[Session Start]"]

        # Git context (branch, commits, status)
        git_ctx = git.get_context_summary(cwd)
        if git_ctx:
            output_parts.extend(git_ctx)

        # Usage summary (sessions, agents, skills)
        if usage := project_context.get_usage_summary():
            output_parts.append(usage)

        # Project type detection
        if ptype := project_context.detect_project_type(cwd):
            output_parts.append(ptype)

        # Start viewer if not running
        if viewer_msg := maybe_start_viewer():
            output_parts.append(viewer_msg)

        # Only return if there's content beyond the header
        return output_parts if len(output_parts) > 1 else []


if __name__ == "__main__":
    SessionStartDispatcher().run()

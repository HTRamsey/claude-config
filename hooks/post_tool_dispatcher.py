#!/home/jonglaser/.claude/data/venv/bin/python3
"""
PostToolUse Dispatcher - Consolidates all PostToolUse hooks into single process.

Benefits:
- Consolidates 9 handlers into single process, avoiding 8 Python interpreter startups
- Shared state and caching
- Typical handler latency: 20-70ms per handler

Environment variables:
- HOOK_PROFILE=1: Enable per-handler timing output to stderr
- HANDLER_TIMEOUT=<ms>: Handler timeout in milliseconds (default: 1000)
"""
import sys
from pathlib import Path
from typing import Any

from dispatcher_base import BaseDispatcher, graceful_main


class PostToolDispatcher(BaseDispatcher):
    """Dispatcher for PostToolUse hooks."""

    DISPATCHER_NAME = "post_tool_dispatcher"
    HOOK_EVENT_NAME = "PostToolUse"

    ALL_HANDLERS = [
        "file_monitor", "batch_operation_detector", "tool_analytics",
        "unified_cache", "suggestion_engine", "build_analyzer",
        "smart_permissions", "state_saver", "subagent_lifecycle"
    ]

    # Tool-to-handler mapping
    # Note: notify_complete moved to async shell script (notify_complete_async.sh)
    # Note: tool_analytics consolidates tool_success_tracker + output_metrics
    TOOL_HANDLERS = {
        "Bash": ["tool_analytics", "build_analyzer", "state_saver"],
        "Grep": ["file_monitor", "tool_analytics"],
        "Glob": ["file_monitor", "tool_analytics"],
        "Read": ["file_monitor", "tool_analytics", "smart_permissions"],
        "Edit": ["batch_operation_detector", "tool_analytics", "smart_permissions"],
        "Write": ["batch_operation_detector", "tool_analytics", "smart_permissions"],
        "Task": ["subagent_lifecycle", "unified_cache", "suggestion_engine", "tool_analytics"],
        "WebFetch": ["unified_cache"],
        "LSP": ["tool_analytics"],
    }

    def _import_handler(self, name: str) -> Any:
        """Import handler by name."""
        if name == "file_monitor":
            from file_monitor import track_file_post
            return track_file_post
        elif name == "batch_operation_detector":
            from batch_operation_detector import detect_batch
            return detect_batch
        elif name == "tool_analytics":
            from tool_analytics import track_tool_analytics
            return track_tool_analytics
        elif name == "unified_cache":
            from unified_cache import handle_exploration_post, handle_research_post
            return (handle_exploration_post, handle_research_post)
        elif name == "suggestion_engine":
            from suggestions import suggest_chain
            return suggest_chain
        elif name == "build_analyzer":
            from build_analyzer import analyze_build_post
            return analyze_build_post
        elif name == "smart_permissions":
            from smart_permissions import smart_permissions_post
            return smart_permissions_post
        elif name == "state_saver":
            from state_saver import handle_post_tool_use
            return handle_post_tool_use
        elif name == "subagent_lifecycle":
            from subagent_lifecycle import handle_complete
            return handle_complete
        return None

    def _execute_handler(self, name: str, handler: Any, ctx: dict) -> dict | None:
        """Execute handler with special-case handling."""
        # Special handling for unified_cache (exploration=0, research=1)
        if name == "unified_cache":
            return self._route_dual_handler(handler, ctx, {"Task": 0, "WebFetch": 1})

        return handler(ctx)


# Singleton dispatcher instance
_dispatcher = PostToolDispatcher()


@graceful_main("post_tool_dispatcher")
def main():
    _dispatcher.run()


if __name__ == "__main__":
    main()

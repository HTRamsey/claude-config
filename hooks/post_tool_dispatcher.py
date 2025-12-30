#!/home/jonglaser/.claude/data/venv/bin/python3
"""
PostToolUse Dispatcher - Consolidates all PostToolUse hooks into single process.

Benefits:
- Consolidates 10 handlers into single process, avoiding 9 Python interpreter startups
- Shared state and caching
- Typical handler latency: 20-70ms per handler

Environment variables:
- HOOK_PROFILE=1: Enable per-handler timing output to stderr
- HANDLER_TIMEOUT=<ms>: Handler timeout in milliseconds (default: 1000)
"""
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
from dispatcher_base import BaseDispatcher, graceful_main


class PostToolDispatcher(BaseDispatcher):
    """Dispatcher for PostToolUse hooks."""

    DISPATCHER_NAME = "post_tool_dispatcher"
    HOOK_EVENT_NAME = "PostToolUse"

    ALL_HANDLERS = [
        "notify_complete", "file_monitor", "batch_operation_detector",
        "tool_success_tracker", "unified_cache", "suggestion_engine",
        "output_metrics", "build_analyzer", "smart_permissions", "state_saver",
        "subagent_lifecycle"
    ]

    # Tool-to-handler mapping
    # Note: notify_complete moved to async shell script (notify_complete_async.sh)
    TOOL_HANDLERS = {
        "Bash": ["tool_success_tracker", "output_metrics", "build_analyzer", "state_saver"],
        "Grep": ["file_monitor", "tool_success_tracker", "output_metrics"],
        "Glob": ["file_monitor", "tool_success_tracker", "output_metrics"],
        "Read": ["file_monitor", "tool_success_tracker", "output_metrics", "smart_permissions"],
        "Edit": ["batch_operation_detector", "tool_success_tracker", "output_metrics", "smart_permissions"],
        "Write": ["batch_operation_detector", "tool_success_tracker", "output_metrics", "smart_permissions"],
        "Task": ["subagent_lifecycle", "unified_cache", "suggestion_engine", "output_metrics"],
        "WebFetch": ["unified_cache"],
        "LSP": ["tool_success_tracker", "output_metrics"],
    }

    def _import_handler(self, name: str) -> Any:
        """Import handler by name."""
        if name == "notify_complete":
            from notify_complete import check_notify
            return check_notify
        elif name == "file_monitor":
            from file_monitor import track_file_post
            return track_file_post
        elif name == "batch_operation_detector":
            from batch_operation_detector import detect_batch
            return detect_batch
        elif name == "tool_success_tracker":
            from tool_success_tracker import track_success
            return track_success
        elif name == "unified_cache":
            from unified_cache import handle_exploration_post, handle_research_post
            return (handle_exploration_post, handle_research_post)
        elif name == "suggestion_engine":
            from suggestion_engine import suggest_chain
            return suggest_chain
        elif name == "output_metrics":
            from output_metrics import track_output_metrics
            return track_output_metrics
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
        # Special handling for unified_cache
        if name == "unified_cache":
            exploration_handler, research_handler = handler
            tool_name = ctx.get("tool_name", "")
            if tool_name == "Task":
                return exploration_handler(ctx)
            elif tool_name == "WebFetch":
                return research_handler(ctx)
            return None

        return handler(ctx)


# Singleton dispatcher instance
_dispatcher = PostToolDispatcher()


@graceful_main("post_tool_dispatcher")
def main():
    _dispatcher.run()


if __name__ == "__main__":
    main()

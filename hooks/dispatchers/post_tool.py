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
import importlib
import sys
from typing import Any

from hooks.dispatchers.base import BaseDispatcher, PostToolStrategy, graceful_main


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

    def _create_result_strategy(self) -> PostToolStrategy:
        """Create PostToolUse result strategy."""
        return PostToolStrategy()

    # Handler import dispatch dictionary
    # Format: "handler_name": ("module_name", "function_name") or ("module_name", ("fn1", "fn2", ...))
    HANDLER_IMPORTS = {
        "file_monitor": ("hooks.handlers.file_monitor", "track_file_post"),
        "batch_operation_detector": ("hooks.handlers.batch_operation_detector", "detect_batch"),
        "tool_analytics": ("hooks.handlers.tool_analytics", "track_tool_analytics"),
        "unified_cache": ("hooks.handlers.unified_cache", ("handle_exploration_post", "handle_research_post")),
        "suggestion_engine": ("hooks.suggestions", "suggest_chain"),
        "build_analyzer": ("hooks.handlers.build_analyzer", "analyze_build_post"),
        "smart_permissions": ("hooks.dispatchers.permission", "smart_permissions_post"),
        "state_saver": ("hooks.handlers.state_saver", "handle_post_tool_use"),
        "subagent_lifecycle": ("hooks.handlers.subagent_lifecycle", "handle_complete"),
    }

    def _import_handler(self, name: str) -> Any:
        """Import handler by name using dispatch dictionary."""
        if name not in self.HANDLER_IMPORTS:
            return None

        module_name, func_spec = self.HANDLER_IMPORTS[name]
        module = importlib.import_module(module_name)

        # Handle single function or tuple of functions
        if isinstance(func_spec, tuple):
            return tuple(getattr(module, fn) for fn in func_spec)
        return getattr(module, func_spec)

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

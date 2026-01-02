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

from hooks.dispatchers.base import BaseDispatcher, PostToolStrategy, RoutingRule, graceful_main


class PostToolDispatcher(BaseDispatcher):
    """Dispatcher for PostToolUse hooks."""

    DISPATCHER_NAME = "post_tool_dispatcher"
    HOOK_EVENT_NAME = "PostToolUse"

    ALL_HANDLERS = [
        "file_monitor", "tool_analytics",
        "unified_cache", "suggestion_engine",
        "smart_permissions", "context_manager", "subagent_lifecycle",
        "notify_complete"
    ]

    # Tool-to-handler mapping
    # Note: tool_analytics consolidates tool_success_tracker + output_metrics + build_analyzer + batch_operation_detector
    TOOL_HANDLERS = {
        "Bash": ["tool_analytics", "context_manager", "notify_complete"],
        "Grep": ["file_monitor", "tool_analytics"],
        "Glob": ["file_monitor", "tool_analytics"],
        "Read": ["file_monitor", "tool_analytics", "smart_permissions"],
        "Edit": ["tool_analytics", "smart_permissions"],
        "Write": ["tool_analytics", "smart_permissions"],
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
        "tool_analytics": ("hooks.handlers.tool_analytics", "track_tool_analytics"),
        "unified_cache": ("hooks.handlers.unified_cache", ("handle_exploration_post", "handle_research_post")),
        "suggestion_engine": ("hooks.handlers.suggestion_engine", "suggest_chain"),
        "smart_permissions": ("hooks.dispatchers.permission", "smart_permissions_post"),
        "context_manager": ("hooks.handlers.context_manager", "handle_post_tool_use"),
        "subagent_lifecycle": ("hooks.handlers.subagent_lifecycle", "handle_complete"),
        "notify_complete": ("hooks.handlers.notify_complete", "notify_complete"),
    }

    def setup_handler_registry(self) -> None:
        """Setup routing rules for dual handlers via registry pattern."""
        # unified_cache: exploration (0) for Task, research (1) for WebFetch
        self._handler_registry.register(
            "unified_cache",
            None,  # Handler loaded via get_handler()
            routing=RoutingRule(
                tool_patterns={"Task": 0, "WebFetch": 1},
                default=0
            )
        )


# Singleton dispatcher instance
_dispatcher = PostToolDispatcher()


@graceful_main("post_tool_dispatcher")
def main():
    _dispatcher.run()


if __name__ == "__main__":
    main()

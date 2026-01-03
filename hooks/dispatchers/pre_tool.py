#!/home/jonglaser/.claude/data/venv/bin/python3
"""
PreToolUse Dispatcher - Consolidates all PreToolUse hooks into single process.

Benefits:
- Consolidates 9 handlers into single process, avoiding 8 Python interpreter startups
- Shared compiled patterns and state
- Typical handler latency: 20-70ms per handler

Environment variables:
- HOOK_PROFILE=1: Enable per-handler timing output to stderr
- HANDLER_TIMEOUT=<ms>: Handler timeout in milliseconds (default: 1000)
"""
import sys

from hooks.dispatchers.base import BaseDispatcher, RoutingRule, PreToolStrategy, graceful_main


class PreToolDispatcher(BaseDispatcher):
    """Dispatcher for PreToolUse hooks."""

    DISPATCHER_NAME = "pre_tool_dispatcher"
    HOOK_EVENT_NAME = "PreToolUse"

    ALL_HANDLERS = [
        "file_protection", "tdd_guard", "dangerous_command_blocker",
        "credential_scanner", "suggestion_engine", "file_monitor",
        "context_manager", "unified_cache", "hierarchical_rules",
        "subagent_lifecycle", "skill_tracker"
    ]

    # Tool-to-handler mapping (order matters - deny hooks first)
    TOOL_HANDLERS = {
        "Read": ["file_protection", "file_monitor", "hierarchical_rules", "suggestion_engine"],
        "Write": ["file_protection", "tdd_guard", "hierarchical_rules", "suggestion_engine", "context_manager"],
        "Edit": ["file_protection", "tdd_guard", "hierarchical_rules", "suggestion_engine", "file_monitor", "context_manager"],
        "Bash": ["dangerous_command_blocker", "credential_scanner", "suggestion_engine"],
        "Grep": ["suggestion_engine"],
        "Glob": ["suggestion_engine"],
        "Task": ["subagent_lifecycle", "unified_cache"],
        "Skill": ["skill_tracker"],
        "WebFetch": ["unified_cache"],
        "LSP": ["suggestion_engine"],
    }

    def _create_result_strategy(self) -> PreToolStrategy:
        """Create PreToolUse result strategy."""
        return PreToolStrategy()

    # Handler import dispatch dictionary
    # All handlers now expose a single entry point function
    HANDLER_IMPORTS = {
        "file_protection": ("hooks.handlers.file_protection", "check_file_protection"),
        "tdd_guard": ("hooks.handlers.tdd_guard", "check_tdd"),
        "dangerous_command_blocker": ("hooks.handlers.dangerous_command_blocker", "check_dangerous_command"),
        "credential_scanner": ("hooks.handlers.credential_scanner", "handle"),
        "suggestion_engine": ("hooks.handlers.suggestion_engine", "handle_pre_tool"),
        "file_monitor": ("hooks.handlers.file_monitor", "track_file_pre"),
        "context_manager": ("hooks.handlers.context_manager", "handle_pre_tool_use"),
        "unified_cache": ("hooks.handlers.unified_cache", ("handle_exploration_pre", "handle_research_pre")),
        "hierarchical_rules": ("hooks.handlers.hierarchical_rules", "check_hierarchical_rules"),
        "subagent_lifecycle": ("hooks.handlers.subagent_lifecycle", "handle_start"),
        "skill_tracker": ("hooks.handlers.subagent_lifecycle", "handle_skill"),
    }

    def setup_handler_registry(self) -> None:
        """Initialize handler registry with routing rules."""
        # Register unified_cache with routing rule (dual handler: exploration vs research)
        self._handler_registry.register(
            "unified_cache",
            None,  # Will be populated by get_handler()
            routing=RoutingRule(
                tool_patterns={"Task": 0, "WebFetch": 1},
                default=0
            )
        )

    def validate_handlers(self) -> None:
        """Extended validation including tiktoken check."""
        super().validate_handlers()
        try:
            import tiktoken
        except ImportError:
            print("[pre_tool_dispatcher] Warning: tiktoken not available, token counting disabled",
                  file=sys.stderr)


# Singleton dispatcher instance
_dispatcher = PreToolDispatcher()


@graceful_main("pre_tool_dispatcher")
def main():
    _dispatcher.run()


if __name__ == "__main__":
    main()

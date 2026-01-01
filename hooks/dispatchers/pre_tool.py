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
import importlib
import sys
from typing import Any

from hooks.dispatchers.base import BaseDispatcher, RoutingRule, PreToolStrategy, graceful_main, log_event


class PreToolDispatcher(BaseDispatcher):
    """Dispatcher for PreToolUse hooks."""

    DISPATCHER_NAME = "pre_tool_dispatcher"
    HOOK_EVENT_NAME = "PreToolUse"

    ALL_HANDLERS = [
        "file_protection", "tdd_guard", "dangerous_command_blocker",
        "credential_scanner", "suggestion_engine", "file_monitor",
        "state_saver", "unified_cache", "usage_tracker", "hierarchical_rules",
        "subagent_lifecycle"
    ]

    # Tool-to-handler mapping (order matters - deny hooks first)
    TOOL_HANDLERS = {
        "Read": ["file_protection", "file_monitor", "hierarchical_rules", "suggestion_engine"],
        "Write": ["file_protection", "tdd_guard", "hierarchical_rules", "suggestion_engine", "state_saver"],
        "Edit": ["file_protection", "tdd_guard", "hierarchical_rules", "suggestion_engine", "file_monitor", "state_saver"],
        "Bash": ["dangerous_command_blocker", "credential_scanner", "suggestion_engine"],
        "Grep": ["suggestion_engine"],
        "Glob": ["suggestion_engine"],
        "Task": ["subagent_lifecycle", "usage_tracker", "unified_cache"],
        "Skill": ["usage_tracker"],
        "WebFetch": ["unified_cache"],
        "LSP": ["suggestion_engine"],
    }

    def _create_result_strategy(self) -> PreToolStrategy:
        """Create PreToolUse result strategy."""
        return PreToolStrategy()

    # Handler import dispatch dictionary
    # Format: "handler_name": ("module_name", "function_name") or ("module_name", ("fn1", "fn2", ...))
    HANDLER_IMPORTS = {
        "file_protection": ("hooks.handlers.file_protection", "check_file_protection"),
        "tdd_guard": ("hooks.handlers.tdd_guard", "check_tdd"),
        "dangerous_command_blocker": ("hooks.handlers.dangerous_command_blocker", "check_dangerous_command"),
        "credential_scanner": ("hooks.handlers.credential_scanner", ("scan_for_sensitive", "get_staged_diff", "is_allowlisted")),
        "suggestion_engine": ("hooks.suggestions", ("suggest_skill", "suggest_subagent", "suggest_optimization")),
        "file_monitor": ("hooks.handlers.file_monitor", "track_file_pre"),
        "state_saver": ("hooks.handlers.state_saver", "handle_pre_tool_use"),
        "unified_cache": ("hooks.handlers.unified_cache", ("handle_exploration_pre", "handle_research_pre")),
        "usage_tracker": ("hooks.handlers.usage_tracker", "handle"),
        "hierarchical_rules": ("hooks.handlers.hierarchical_rules", "check_hierarchical_rules"),
        "subagent_lifecycle": ("hooks.handlers.subagent_lifecycle", "handle_start"),
    }

    def _credential_scanner_executor(self, name: str, handler: Any, ctx: dict) -> dict | None:
        """Custom executor for credential_scanner dual handler."""
        scan_func, get_diff, is_allowed = handler
        command = ctx.get("tool_input", {}).get("command", "")
        if not command.strip().startswith("git commit"):
            return None
        diff_content, staged_files = get_diff()
        if diff_content:
            non_allowlisted = [f for f in staged_files if not is_allowed(f)]
            if non_allowlisted:
                findings = scan_func(diff_content)
                if findings:
                    unique_types = list(set(n for n, _ in findings))[:5]
                    return {
                        "hookSpecificOutput": {
                            "hookEventName": "PreToolUse",
                            "permissionDecision": "deny",
                            "permissionDecisionReason": (
                                f"Potential credentials detected: {', '.join(unique_types)}. "
                                f"Files: {', '.join(non_allowlisted[:3])}. "
                                "Review with: git diff --cached"
                            )
                        }
                    }
        return None

    def _suggestion_engine_executor(self, name: str, handler: Any, ctx: dict) -> dict | None:
        """Custom executor for suggestion_engine triple handler."""
        suggest_skill, suggest_subagent, suggest_optimization = handler
        tool_name = ctx.get("tool_name", "")
        if tool_name in ("Write", "Edit"):
            return suggest_skill(ctx)
        elif tool_name in ("Grep", "Glob", "Read"):
            return suggest_subagent(ctx) or suggest_optimization(ctx)
        elif tool_name == "Bash":
            return suggest_optimization(ctx)
        return None

    def setup_handler_registry(self) -> None:
        """Initialize handler registry with routing rules and custom executors."""
        # Register credential_scanner with custom executor (handles 3-tuple unpacking)
        self._handler_registry.register(
            "credential_scanner",
            None,  # Will be populated by get_handler()
            executor=self._credential_scanner_executor
        )

        # Register suggestion_engine with custom executor (handles tool-specific routing)
        self._handler_registry.register(
            "suggestion_engine",
            None,  # Will be populated by get_handler()
            executor=self._suggestion_engine_executor
        )

        # Register unified_cache with routing rule (dual handler: exploration vs research)
        self._handler_registry.register(
            "unified_cache",
            None,  # Will be populated by get_handler()
            routing=RoutingRule(
                tool_patterns={"Task": 0, "WebFetch": 1},
                default=0
            )
        )

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
        """Execute handler with registry-driven special-case handling.

        Delegates to custom executors and routing rules registered in setup_handler_registry().
        Falls back to base implementation for standard handlers.
        """
        return super()._execute_handler(name, handler, ctx)

    def _should_terminate(self, result: dict, handler_name: str, tool_name: str) -> bool:
        """PreToolUse terminates on deny decisions."""
        hook_output = result.get("hookSpecificOutput", {})
        if hook_output.get("permissionDecision") == "deny":
            log_event(self.DISPATCHER_NAME, "denied", {
                "tool": tool_name,
                "handler": handler_name
            })
            return True
        return False

    def _extract_message(self, hook_output: dict) -> str:
        """Extract permissionDecisionReason for PreToolUse."""
        return hook_output.get("permissionDecisionReason", "")

    def _build_result(self, messages: list[str]) -> dict | None:
        """Build PreToolUse result with allow decision."""
        if messages:
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "allow",
                    "permissionDecisionReason": " | ".join(messages[:3])
                }
            }
        return None

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

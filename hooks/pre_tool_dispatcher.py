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
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
from dispatcher_base import BaseDispatcher, graceful_main, log_event


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

    def _import_handler(self, name: str) -> Any:
        """Import handler by name."""
        if name == "file_protection":
            from file_protection import check_file_protection
            return check_file_protection
        elif name == "tdd_guard":
            from tdd_guard import check_tdd
            return check_tdd
        elif name == "dangerous_command_blocker":
            from dangerous_command_blocker import check_dangerous_command
            return check_dangerous_command
        elif name == "credential_scanner":
            from credential_scanner import scan_for_sensitive, get_staged_diff, is_allowlisted
            return (scan_for_sensitive, get_staged_diff, is_allowlisted)
        elif name == "suggestion_engine":
            from suggestion_engine import suggest_skill, suggest_subagent, suggest_optimization
            return (suggest_skill, suggest_subagent, suggest_optimization)
        elif name == "file_monitor":
            from file_monitor import track_file_pre
            return track_file_pre
        elif name == "state_saver":
            from state_saver import handle_pre_tool_use as save_checkpoint
            return save_checkpoint
        elif name == "unified_cache":
            from unified_cache import handle_exploration_pre, handle_research_pre
            return (handle_exploration_pre, handle_research_pre)
        elif name == "usage_tracker":
            from usage_tracker import track_usage
            return track_usage
        elif name == "hierarchical_rules":
            from hierarchical_rules import check_hierarchical_rules
            return check_hierarchical_rules
        elif name == "subagent_lifecycle":
            from subagent_lifecycle import handle_start
            return handle_start
        return None

    def _execute_handler(self, name: str, handler: Any, ctx: dict) -> dict | None:
        """Execute handler with special-case handling."""
        # Special handling for credential_scanner
        if name == "credential_scanner":
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

        # Special handling for suggestion_engine
        if name == "suggestion_engine":
            suggest_skill, suggest_subagent, suggest_optimization = handler
            tool_name = ctx.get("tool_name", "")
            if tool_name in ("Write", "Edit"):
                return suggest_skill(ctx)
            elif tool_name in ("Grep", "Glob", "Read"):
                return suggest_subagent(ctx) or suggest_optimization(ctx)
            elif tool_name == "Bash":
                return suggest_optimization(ctx)
            return None

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

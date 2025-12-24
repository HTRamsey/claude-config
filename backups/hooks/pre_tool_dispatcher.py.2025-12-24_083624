#!/home/jonglaser/.claude/venv/bin/python3
"""
PreToolUse Dispatcher - Consolidates all PreToolUse hooks into single process.

STATUS: READY - All hooks export handler functions.

Benefits:
- Single Python process startup instead of 10+
- Shared compiled patterns and state
- Faster hook execution (100-300ms savings)

Dispatches to handler functions based on tool name matching.
"""
import json
import sys
from pathlib import Path

# Import shared utilities
sys.path.insert(0, str(Path(__file__).parent))
try:
    from hook_utils import graceful_main, log_event
    HAS_UTILS = True
except ImportError:
    HAS_UTILS = False
    def graceful_main(name):
        def decorator(func):
            return func
        return decorator
    def log_event(*args, **kwargs):
        pass

# Import handler modules (lazy import for speed)
_handlers = {}

def get_handler(name: str):
    """Lazy-load handler module."""
    if name not in _handlers:
        try:
            if name == "file_protection":
                from file_protection import check_file_protection
                _handlers[name] = check_file_protection
            elif name == "tdd_guard":
                from tdd_guard import check_tdd
                _handlers[name] = check_tdd
            elif name == "dangerous_command_blocker":
                from dangerous_command_blocker import check_dangerous_command
                _handlers[name] = check_dangerous_command
            elif name == "credential_scanner":
                from credential_scanner import scan_for_sensitive, get_staged_diff, is_allowlisted
                _handlers[name] = (scan_for_sensitive, get_staged_diff, is_allowlisted)
            elif name == "suggest_tool_optimization":
                from suggest_tool_optimization import suggest_optimization
                _handlers[name] = suggest_optimization
            elif name == "file_access_tracker":
                from file_access_tracker import track_file_access
                _handlers[name] = track_file_access
            elif name == "preread_summarize":
                from preread_summarize import check_preread
                _handlers[name] = check_preread
            elif name == "context_checkpoint":
                from context_checkpoint import save_checkpoint
                _handlers[name] = save_checkpoint
            elif name == "suggest_subagent":
                from suggest_subagent import suggest_subagent
                _handlers[name] = suggest_subagent
            elif name == "exploration_cache":
                from exploration_cache import handle_pre_tool_use as cache_lookup
                _handlers[name] = cache_lookup
            elif name == "research_cache":
                from research_cache import handle_pre_tool_use as research_lookup
                _handlers[name] = research_lookup
            elif name == "usage_tracker":
                from usage_tracker import track_usage
                _handlers[name] = track_usage
            elif name == "skill_suggester":
                from skill_suggester import suggest_skill
                _handlers[name] = suggest_skill
            else:
                _handlers[name] = None
        except ImportError as e:
            log_event("pre_tool_dispatcher", "import_error", {"handler": name, "error": str(e)})
            _handlers[name] = None
    return _handlers.get(name)


# Tool-to-handler mapping (order matters - deny hooks first)
TOOL_HANDLERS = {
    "Read": ["file_protection", "file_access_tracker", "preread_summarize", "suggest_tool_optimization", "suggest_subagent"],
    "Write": ["file_protection", "tdd_guard", "skill_suggester", "context_checkpoint"],
    "Edit": ["file_protection", "tdd_guard", "skill_suggester", "file_access_tracker", "context_checkpoint"],
    "Bash": ["dangerous_command_blocker", "credential_scanner", "suggest_tool_optimization"],
    "Grep": ["suggest_tool_optimization", "suggest_subagent"],
    "Glob": ["suggest_subagent"],
    "Task": ["usage_tracker", "exploration_cache"],
    "Skill": ["usage_tracker"],
    "WebFetch": ["research_cache"],
}


def run_handler(name: str, ctx: dict) -> dict | None:
    """Run a single handler and return its result."""
    handler = get_handler(name)
    if handler is None:
        return None

    try:
        # Special handling for credential_scanner (needs full context check)
        if name == "credential_scanner":
            scan_func, get_diff, is_allowed = handler
            command = ctx.get("tool_input", {}).get("command", "")
            if not command.strip().startswith("git commit"):
                return None
            diff_content, staged_files = get_diff()
            if not diff_content:
                return None
            non_allowlisted = [f for f in staged_files if not is_allowed(f)]
            if not non_allowlisted:
                return None
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

        # For other handlers, call directly with context
        return handler(ctx)

    except Exception as e:
        log_event("pre_tool_dispatcher", "handler_error", {"handler": name, "error": str(e)})
        return None


def dispatch(ctx: dict) -> dict | None:
    """Dispatch to appropriate handlers based on tool name."""
    tool_name = ctx.get("tool_name", "")

    handlers = TOOL_HANDLERS.get(tool_name, [])
    if not handlers:
        return None

    messages = []

    for handler_name in handlers:
        result = run_handler(handler_name, ctx)

        if result and isinstance(result, dict):
            hook_output = result.get("hookSpecificOutput", {})
            decision = hook_output.get("permissionDecision", "")

            # Deny stops immediately
            if decision == "deny":
                log_event("pre_tool_dispatcher", "denied", {
                    "tool": tool_name,
                    "handler": handler_name
                })
                return result

            # Collect messages from allow/info responses
            reason = hook_output.get("permissionDecisionReason", "")
            if reason:
                messages.append(reason)

    # If we have messages but no deny, return combined info
    if messages:
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "permissionDecisionReason": " | ".join(messages[:3])
            }
        }

    return None


@graceful_main("pre_tool_dispatcher")
def main():
    try:
        ctx = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    result = dispatch(ctx)
    if result:
        print(json.dumps(result))

    sys.exit(0)


if __name__ == "__main__":
    main()

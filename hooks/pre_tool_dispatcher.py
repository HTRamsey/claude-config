#!/home/jonglaser/.claude/venv/bin/python3
"""
PreToolUse Dispatcher - Consolidates all PreToolUse hooks into single process.

STATUS: READY - All hooks export handler functions.

Benefits:
- Consolidates 9 handlers into single process, avoiding 8 Python interpreter startups
- Shared compiled patterns and state
- Typical handler latency: 20-70ms per handler

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
            elif name == "suggestion_engine":
                from suggestion_engine import suggest_skill, suggest_subagent, suggest_optimization
                _handlers[name] = (suggest_skill, suggest_subagent, suggest_optimization)
            elif name == "file_monitor":
                from file_monitor import track_file_pre
                _handlers[name] = track_file_pre
            elif name == "state_saver":
                from state_saver import handle_pre_tool_use as save_checkpoint
                _handlers[name] = save_checkpoint
            elif name == "unified_cache":
                from unified_cache import handle_exploration_pre, handle_research_pre
                _handlers[name] = (handle_exploration_pre, handle_research_pre)
            elif name == "usage_tracker":
                from usage_tracker import track_usage
                _handlers[name] = track_usage
            elif name == "hierarchical_rules":
                from hierarchical_rules import check_hierarchical_rules
                _handlers[name] = check_hierarchical_rules
            else:
                _handlers[name] = None
        except ImportError as e:
            log_event("pre_tool_dispatcher", "import_error", {"handler": name, "error": str(e)})
            _handlers[name] = None
    return _handlers.get(name)


# All handler names for validation
ALL_HANDLERS = [
    "file_protection", "tdd_guard", "dangerous_command_blocker",
    "credential_scanner", "suggestion_engine", "file_monitor",
    "state_saver", "unified_cache", "usage_tracker", "hierarchical_rules"
]

def validate_handlers():
    """Validate all handlers can be imported and are callable."""
    failed = []
    for name in ALL_HANDLERS:
        handler = get_handler(name)
        if handler is None and name in _handlers:
            failed.append(name)
        elif handler is not None and not callable(handler):
            # Handle tuple of handlers (like credential_scanner, suggestion_engine)
            if isinstance(handler, tuple):
                if not all(callable(h) for h in handler):
                    failed.append(f"{name} (not all callable)")
            else:
                failed.append(f"{name} (not callable)")
    if failed:
        log_event("pre_tool_dispatcher", "startup_validation", {
            "failed_handlers": failed,
            "count": len(failed)
        })
        # Also print to stderr for visibility
        print(f"[pre_tool_dispatcher] Warning: {len(failed)} handlers failed to import: {', '.join(failed)}", file=sys.stderr)

    # Check optional dependencies
    try:
        import tiktoken
    except ImportError:
        print("[pre_tool_dispatcher] Warning: tiktoken not available, token counting disabled", file=sys.stderr)


# Tool-to-handler mapping (order matters - deny hooks first)
TOOL_HANDLERS = {
    "Read": ["file_protection", "file_monitor", "hierarchical_rules", "suggestion_engine"],
    "Write": ["file_protection", "tdd_guard", "hierarchical_rules", "suggestion_engine", "state_saver"],
    "Edit": ["file_protection", "tdd_guard", "hierarchical_rules", "suggestion_engine", "file_monitor", "state_saver"],
    "Bash": ["dangerous_command_blocker", "credential_scanner", "suggestion_engine"],
    "Grep": ["suggestion_engine"],
    "Glob": ["suggestion_engine"],
    "Task": ["usage_tracker", "unified_cache"],
    "Skill": ["usage_tracker"],
    "WebFetch": ["unified_cache"],
}


def is_hook_disabled(name: str) -> bool:
    """Check if hook is disabled globally or for current session."""
    import os
    data_dir = Path.home() / ".claude" / "data"

    # Check session override first (takes precedence)
    session_hooks_dir = data_dir / "session-hooks"
    session_id = os.environ.get("CLAUDE_SESSION_ID", "")
    if not session_id:
        session_file = data_dir / ".current-session"
        if session_file.exists():
            session_id = session_file.read_text().strip()

    if session_id:
        session_override_file = session_hooks_dir / f"{session_id}.json"
        if session_override_file.exists():
            try:
                session_data = json.loads(session_override_file.read_text())
                override = session_data.get("overrides", {}).get(name)
                if override is False:
                    return True  # Disabled for session
                elif override is True:
                    return False  # Enabled for session (overrides global)
            except (json.JSONDecodeError, IOError):
                pass

    # Check global disabled list
    config_file = data_dir / "hook-config.json"
    if config_file.exists():
        try:
            config = json.loads(config_file.read_text())
            if name in config.get("disabled", []):
                return True
        except (json.JSONDecodeError, IOError):
            pass

    return False


def run_handler(name: str, ctx: dict) -> dict | None:
    """Run a single handler and return its result."""
    import time

    # Check if hook is disabled
    if is_hook_disabled(name):
        log_event("pre_tool_dispatcher", "handler_skipped", {"handler": name, "reason": "disabled"})
        return None

    handler = get_handler(name)
    if handler is None:
        return None

    start_time = time.perf_counter()
    result = None
    error = None

    try:
        # Special handling for credential_scanner (needs full context check)
        if name == "credential_scanner":
            scan_func, get_diff, is_allowed = handler
            command = ctx.get("tool_input", {}).get("command", "")
            if not command.strip().startswith("git commit"):
                pass  # result stays None
            else:
                diff_content, staged_files = get_diff()
                if diff_content:
                    non_allowlisted = [f for f in staged_files if not is_allowed(f)]
                    if non_allowlisted:
                        findings = scan_func(diff_content)
                        if findings:
                            unique_types = list(set(n for n, _ in findings))[:5]
                            result = {
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

        # Special handling for suggestion_engine (consolidates skill, subagent, optimization)
        elif name == "suggestion_engine":
            suggest_skill, suggest_subagent, suggest_optimization = handler
            tool_name = ctx.get("tool_name", "")
            if tool_name in ("Write", "Edit"):
                result = suggest_skill(ctx)
            elif tool_name in ("Grep", "Glob", "Read"):
                result = suggest_subagent(ctx) or suggest_optimization(ctx)
            elif tool_name == "Bash":
                result = suggest_optimization(ctx)

        # Special handling for unified_cache (has separate handlers for Task vs WebFetch)
        elif name == "unified_cache":
            exploration_handler, research_handler = handler
            tool_name = ctx.get("tool_name", "")
            if tool_name == "Task":
                result = exploration_handler(ctx)
            elif tool_name == "WebFetch":
                result = research_handler(ctx)

        # For other handlers, call directly with context
        else:
            result = handler(ctx)

    except Exception as e:
        error = str(e)
        log_event("pre_tool_dispatcher", "handler_error", {"handler": name, "error": error})

    # Log timing
    elapsed_ms = (time.perf_counter() - start_time) * 1000
    log_event("pre_tool_dispatcher", "handler_timing", {
        "handler": name,
        "elapsed_ms": round(elapsed_ms, 2),
        "tool": ctx.get("tool_name", ""),
        "success": error is None
    })

    return result


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


_validated = False

@graceful_main("pre_tool_dispatcher")
def main():
    global _validated
    if not _validated:
        validate_handlers()
        _validated = True

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

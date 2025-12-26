#!/home/jonglaser/.claude/venv/bin/python3
"""
PostToolUse Dispatcher - Consolidates all PostToolUse hooks into single process.

STATUS: READY - All hooks export handler functions.

Benefits:
- Consolidates 10 handlers into single process, avoiding 9 Python interpreter startups
- Shared state and caching
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

# Lazy-loaded handler modules
_handlers = {}

def get_handler(name: str):
    """Lazy-load handler module."""
    if name not in _handlers:
        try:
            if name == "notify_complete":
                from notify_complete import check_notify
                _handlers[name] = check_notify
            elif name == "file_monitor":
                from file_monitor import track_file_post
                _handlers[name] = track_file_post
            elif name == "batch_operation_detector":
                from batch_operation_detector import detect_batch
                _handlers[name] = detect_batch
            elif name == "tool_success_tracker":
                from tool_success_tracker import track_success
                _handlers[name] = track_success
            elif name == "unified_cache":
                from unified_cache import handle_exploration_post, handle_research_post
                _handlers[name] = (handle_exploration_post, handle_research_post)
            elif name == "suggestion_engine":
                from suggestion_engine import suggest_chain
                _handlers[name] = suggest_chain
            elif name == "output_metrics":
                from output_metrics import track_output_metrics
                _handlers[name] = track_output_metrics
            elif name == "build_analyzer":
                from build_analyzer import analyze_build_post
                _handlers[name] = analyze_build_post
            elif name == "smart_permissions":
                from smart_permissions import smart_permissions_post
                _handlers[name] = smart_permissions_post
            elif name == "state_saver":
                from state_saver import handle_post_tool_use
                _handlers[name] = handle_post_tool_use
            else:
                _handlers[name] = None
        except ImportError as e:
            log_event("post_tool_dispatcher", "import_error", {"handler": name, "error": str(e)})
            _handlers[name] = None
    return _handlers.get(name)


# All handler names for validation
ALL_HANDLERS = [
    "notify_complete", "file_monitor", "batch_operation_detector",
    "tool_success_tracker", "unified_cache", "suggestion_engine",
    "output_metrics", "build_analyzer", "smart_permissions", "state_saver"
]

def validate_handlers():
    """Validate all handlers can be imported. Called once at startup."""
    failed = []
    for name in ALL_HANDLERS:
        handler = get_handler(name)
        if handler is None and name in _handlers:
            failed.append(name)
    if failed:
        log_event("post_tool_dispatcher", "startup_validation", {
            "failed_handlers": failed,
            "count": len(failed)
        })
        print(f"[post_tool_dispatcher] Warning: {len(failed)} handlers failed to import: {', '.join(failed)}", file=sys.stderr)


# Tool-to-handler mapping
TOOL_HANDLERS = {
    # notify_complete moved to async shell script (notify_complete_async.sh)
    "Bash": ["tool_success_tracker", "output_metrics", "build_analyzer", "state_saver"],
    "Grep": ["file_monitor", "tool_success_tracker", "output_metrics"],
    "Glob": ["file_monitor", "tool_success_tracker", "output_metrics"],
    "Read": ["file_monitor", "tool_success_tracker", "output_metrics", "smart_permissions"],
    "Edit": ["batch_operation_detector", "tool_success_tracker", "output_metrics", "smart_permissions"],
    "Write": ["batch_operation_detector", "tool_success_tracker", "output_metrics", "smart_permissions"],
    "Task": ["unified_cache", "suggestion_engine", "output_metrics"],
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
        log_event("post_tool_dispatcher", "handler_skipped", {"handler": name, "reason": "disabled"})
        return None

    handler = get_handler(name)
    if handler is None:
        return None

    start_time = time.perf_counter()
    result = None
    error = None

    try:
        # Special handling for unified_cache (has separate handlers for Task vs WebFetch)
        if name == "unified_cache":
            exploration_handler, research_handler = handler
            tool_name = ctx.get("tool_name", "")
            if tool_name == "Task":
                result = exploration_handler(ctx)
            elif tool_name == "WebFetch":
                result = research_handler(ctx)
        else:
            result = handler(ctx)
    except Exception as e:
        error = str(e)
        log_event("post_tool_dispatcher", "handler_error", {"handler": name, "error": error})

    # Log timing
    elapsed_ms = (time.perf_counter() - start_time) * 1000
    log_event("post_tool_dispatcher", "handler_timing", {
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
            message = hook_output.get("message", "")
            if message:
                messages.append(message)

    # PostToolUse hooks don't block, just collect messages
    if messages:
        return {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "message": " | ".join(messages[:3])
            }
        }

    return None


_validated = False

@graceful_main("post_tool_dispatcher")
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

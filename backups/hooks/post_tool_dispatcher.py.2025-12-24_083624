#!/home/jonglaser/.claude/venv/bin/python3
"""
PostToolUse Dispatcher - Consolidates all PostToolUse hooks into single process.

STATUS: READY - All hooks export handler functions.

Benefits:
- Single Python process startup instead of 8+
- Shared state and caching
- Faster hook execution (80-200ms savings)

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
            elif name == "file_access_tracker":
                from file_access_tracker import track_post_access
                _handlers[name] = track_post_access
            elif name == "batch_operation_detector":
                from batch_operation_detector import detect_batch
                _handlers[name] = detect_batch
            elif name == "tool_success_tracker":
                from tool_success_tracker import track_success
                _handlers[name] = track_success
            elif name == "exploration_cache":
                from exploration_cache import handle_post_tool_use as cache_store
                _handlers[name] = cache_store
            elif name == "agent_chaining":
                from agent_chaining import suggest_chain
                _handlers[name] = suggest_chain
            elif name == "research_cache":
                from research_cache import handle_post_tool_use as research_store
                _handlers[name] = research_store
            elif name == "token_tracker":
                from token_tracker import track_tokens
                _handlers[name] = track_tokens
            elif name == "output_size_monitor":
                from output_size_monitor import check_output_size
                _handlers[name] = check_output_size
            else:
                _handlers[name] = None
        except ImportError as e:
            log_event("post_tool_dispatcher", "import_error", {"handler": name, "error": str(e)})
            _handlers[name] = None
    return _handlers.get(name)


# Tool-to-handler mapping
TOOL_HANDLERS = {
    "Bash": ["notify_complete", "tool_success_tracker", "token_tracker", "output_size_monitor"],
    "Grep": ["file_access_tracker", "tool_success_tracker", "token_tracker", "output_size_monitor"],
    "Glob": ["file_access_tracker", "tool_success_tracker", "token_tracker", "output_size_monitor"],
    "Read": ["file_access_tracker", "tool_success_tracker", "token_tracker", "output_size_monitor"],
    "Edit": ["batch_operation_detector", "tool_success_tracker", "token_tracker", "output_size_monitor"],
    "Write": ["batch_operation_detector", "tool_success_tracker", "token_tracker", "output_size_monitor"],
    "Task": ["exploration_cache", "agent_chaining", "token_tracker", "output_size_monitor"],
    "WebFetch": ["research_cache"],
}


def run_handler(name: str, ctx: dict) -> dict | None:
    """Run a single handler and return its result."""
    handler = get_handler(name)
    if handler is None:
        return None

    try:
        return handler(ctx)
    except Exception as e:
        log_event("post_tool_dispatcher", "handler_error", {"handler": name, "error": str(e)})
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


@graceful_main("post_tool_dispatcher")
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

#!/home/jonglaser/.claude/data/venv/bin/python3
"""
UserPromptSubmit Dispatcher - Consolidates all UserPromptSubmit hooks.

Benefits:
- Consolidates 2 handlers into single process
- Shared tiktoken encoder initialization
- ~50ms savings per user message

Dispatches to:
- context_monitor: Check context size, warn/backup at thresholds
- usage_tracker: Track slash command usage
"""
import json
import sys
from pathlib import Path

# Import shared utilities
sys.path.insert(0, str(Path(__file__).parent))
try:
    from hook_utils import graceful_main, log_event, is_hook_disabled
    HAS_UTILS = True
except ImportError:
    HAS_UTILS = False
    def graceful_main(name):
        def decorator(func):
            return func
        return decorator
    def log_event(*args, **kwargs):
        pass
    def is_hook_disabled(name):
        return False

# Lazy-loaded handlers
_handlers = {}


def get_handler(name: str):
    """Lazy-load handler module."""
    if name not in _handlers:
        try:
            if name == "context_monitor":
                from context_monitor import check_context
                _handlers[name] = check_context
            elif name == "usage_tracker":
                from usage_tracker import track_usage
                _handlers[name] = track_usage
            else:
                _handlers[name] = None
        except ImportError as e:
            log_event("user_prompt_dispatcher", "import_error", {"handler": name, "error": str(e)})
            _handlers[name] = None
    return _handlers.get(name)


# Handler order (context_monitor first for early warning)
HANDLERS = ["context_monitor", "usage_tracker"]


def run_handler(name: str, ctx: dict) -> dict | None:
    """Run a single handler and return its result."""
    import time

    if is_hook_disabled(name):
        log_event("user_prompt_dispatcher", "handler_skipped", {"handler": name, "reason": "disabled"})
        return None

    handler = get_handler(name)
    if handler is None:
        return None

    start_time = time.perf_counter()
    result = None
    error = None

    try:
        result = handler(ctx)
    except Exception as e:
        error = str(e)
        log_event("user_prompt_dispatcher", "handler_error", {"handler": name, "error": error})

    elapsed_ms = (time.perf_counter() - start_time) * 1000
    log_event("user_prompt_dispatcher", "handler_timing", {
        "handler": name,
        "elapsed_ms": round(elapsed_ms, 2),
        "success": error is None
    })

    return result


def dispatch(ctx: dict) -> dict | None:
    """Dispatch to all UserPromptSubmit handlers."""
    messages = []

    for handler_name in HANDLERS:
        result = run_handler(handler_name, ctx)

        if result and isinstance(result, dict):
            message = result.get("message", "")
            if message:
                messages.append(message)

    if messages:
        return {"message": "\n".join(messages)}

    return None


@graceful_main("user_prompt_dispatcher")
def main():
    try:
        ctx = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    result = dispatch(ctx)
    if result and result.get("message"):
        print(result["message"])

    sys.exit(0)


if __name__ == "__main__":
    main()

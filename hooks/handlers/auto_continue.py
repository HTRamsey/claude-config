"""
Auto-continue handler - evaluate if Claude should continue working.

Provides continuation detection and rate limiting for stop dispatcher.
"""
import time

from hooks.config import Timeouts, Thresholds, AutoContinue
from hooks.hook_utils import log_event, get_last_assistant_content
from hooks.hook_sdk import HookState


MAX_CONTINUATIONS = Thresholds.MAX_CONTINUATIONS
WINDOW_SECONDS = Timeouts.CONTINUE_WINDOW

# State management using HookState
_state = HookState("auto-continue", use_session=False)


def get_incomplete_patterns():
    """Get compiled patterns indicating incomplete work."""
    return AutoContinue.get_incomplete()


def get_complete_patterns():
    """Get compiled patterns indicating completed work."""
    return AutoContinue.get_complete()


def load_continue_state() -> dict:
    """Load rate limit state."""
    return _state.load(default={"continuations": [], "last_reset": time.time()})


def save_continue_state(state: dict) -> None:
    """Save rate limit state."""
    _state.save(state)


def check_rate_limit() -> bool:
    """Check if we can continue (within rate limit).

    Returns:
        True if continuation is allowed, False if rate limited.
    """
    state = load_continue_state()
    now = time.time()

    window_start = now - WINDOW_SECONDS
    state["continuations"] = [t for t in state["continuations"] if t > window_start]

    if len(state["continuations"]) >= MAX_CONTINUATIONS:
        log_event("auto_continue", "rate_limited", {
            "count": len(state["continuations"]),
            "max": MAX_CONTINUATIONS
        })
        return False

    return True


def record_continuation() -> None:
    """Record that we triggered a continuation."""
    state = load_continue_state()
    state["continuations"].append(time.time())
    save_continue_state(state)


def extract_last_messages(ctx: dict, count: int = 10) -> list:
    """Extract last N messages from transcript context.

    Args:
        ctx: Context dict with messages or transcript_path
        count: Number of messages to extract

    Returns:
        List of message dicts.
    """
    messages = ctx.get("messages", [])
    if messages:
        return messages[-count:]

    transcript_path = ctx.get("transcript_path", "")
    if not transcript_path:
        return []

    # Use transcript utilities for parsing
    from hooks.hook_utils.transcript import extract_messages
    all_messages = extract_messages(transcript_path, tail=count * 5)
    # Filter to user/assistant only
    filtered = [m for m in all_messages if m.get("role") in ("user", "assistant")]
    return filtered[-count:]


def heuristic_should_continue(messages: list) -> tuple[bool, str]:
    """Use heuristics to check if work should continue.

    Args:
        messages: List of message dicts

    Returns:
        Tuple of (should_continue, reason)
    """
    if not messages:
        return False, "no messages"

    last_assistant = None
    for msg in reversed(messages):
        if msg.get("type") == "assistant" or msg.get("role") == "assistant":
            content = msg.get("content", "")
            if isinstance(content, list):
                content = " ".join(str(c.get("text", "")) for c in content if isinstance(c, dict))
            last_assistant = content.lower()
            break

    if not last_assistant:
        return False, "no assistant message"

    for pattern in get_complete_patterns():
        if pattern.search(last_assistant):
            return False, f"completion pattern: {pattern.pattern}"

    for pattern in get_incomplete_patterns():
        if pattern.search(last_assistant):
            return True, f"incomplete pattern: {pattern.pattern}"

    return False, "no clear signal"


def check_auto_continue(ctx: dict) -> dict | None:
    """Check if work should auto-continue.

    Args:
        ctx: Context dict with messages or transcript_path

    Returns:
        Dict with "result": "continue" if should continue, else None.
    """
    if not check_rate_limit():
        return None

    messages = extract_last_messages(ctx)
    should_continue, reason = heuristic_should_continue(messages)

    log_event("auto_continue", "evaluated", {
        "should_continue": should_continue,
        "reason": reason,
        "message_count": len(messages)
    })

    if should_continue:
        record_continuation()
        return {
            "result": "continue",
            "reason": f"[Auto-continue] {reason}"
        }

    return None

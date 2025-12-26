#!/home/jonglaser/.claude/venv/bin/python3
"""
Auto-Continue Hook - Evaluates whether Claude should continue working.

Runs on Stop event. Uses a fast model (Haiku) to evaluate if there are
obvious next steps that Claude should continue with automatically.

Rate limited to prevent infinite loops.
"""
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from hook_utils import graceful_main, log_event

# Configuration
STATE_FILE = Path.home() / ".claude/data/auto-continue-state.json"
MAX_CONTINUATIONS = 3  # Max per window
WINDOW_SECONDS = 300   # 5 minutes
MODEL = os.environ.get("DOUBLE_SHOT_LATTE_MODEL", "claude-haiku-3-5-20241022")

# Patterns that suggest work is incomplete
INCOMPLETE_PATTERNS = [
    "todo list",
    "next step",
    "pending",
    "in_progress",
    "will now",
    "let me continue",
    "moving on to",
    "batch",
    "item",
]

# Patterns that suggest work is complete or needs input
COMPLETE_PATTERNS = [
    "done",
    "complete",
    "finished",
    "waiting for",
    "need your input",
    "what would you like",
    "shall i",
    "would you like",
    "please confirm",
    "let me know",
]


def load_state() -> dict:
    """Load rate limit state."""
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {"continuations": [], "last_reset": time.time()}


def save_state(state: dict):
    """Save rate limit state."""
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(STATE_FILE, "w") as f:
            json.dump(state, f)
    except Exception:
        pass


def check_rate_limit() -> bool:
    """Check if we can continue (within rate limit)."""
    state = load_state()
    now = time.time()

    # Clean old entries outside window
    window_start = now - WINDOW_SECONDS
    state["continuations"] = [t for t in state["continuations"] if t > window_start]

    if len(state["continuations"]) >= MAX_CONTINUATIONS:
        log_event("auto_continue", "rate_limited", {
            "count": len(state["continuations"]),
            "max": MAX_CONTINUATIONS
        })
        return False

    return True


def record_continuation():
    """Record that we triggered a continuation."""
    state = load_state()
    state["continuations"].append(time.time())
    save_state(state)


def extract_last_messages(ctx: dict, count: int = 10) -> list:
    """Extract last N messages from transcript context."""
    # The Stop event context may include recent messages
    messages = ctx.get("messages", [])
    if messages:
        return messages[-count:]

    # Fallback: check transcript_path
    transcript_path = ctx.get("transcript_path", "")
    if not transcript_path:
        return []

    try:
        with open(transcript_path) as f:
            lines = f.readlines()[-count * 5:]  # Rough estimate
            messages = []
            for line in lines:
                try:
                    entry = json.loads(line)
                    if entry.get("type") in ("human", "assistant"):
                        messages.append(entry)
                except json.JSONDecodeError:
                    continue
            return messages[-count:]
    except Exception:
        return []


def heuristic_should_continue(messages: list) -> tuple[bool, str]:
    """Use heuristics to check if work should continue.

    Returns (should_continue, reason)
    """
    if not messages:
        return False, "no messages"

    # Get last assistant message
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

    # Check for completion patterns (stop signals)
    for pattern in COMPLETE_PATTERNS:
        if pattern in last_assistant:
            return False, f"completion pattern: {pattern}"

    # Check for incomplete patterns (continue signals)
    for pattern in INCOMPLETE_PATTERNS:
        if pattern in last_assistant:
            return True, f"incomplete pattern: {pattern}"

    # Default: don't continue (safer)
    return False, "no clear signal"


def handle_stop(ctx: dict) -> dict | None:
    """Handle Stop event - evaluate if we should continue."""
    # Check rate limit first
    if not check_rate_limit():
        return None

    # Extract recent messages
    messages = extract_last_messages(ctx)

    # Use heuristics (fast, no API call needed)
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


@graceful_main("auto_continue")
def main():
    try:
        ctx = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    # Only handle Stop events
    event_type = ctx.get("event_type", "")
    if event_type != "Stop":
        sys.exit(0)

    result = handle_stop(ctx)
    if result:
        print(json.dumps(result))

    sys.exit(0)


if __name__ == "__main__":
    main()

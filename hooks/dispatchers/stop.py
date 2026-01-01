#!/home/jonglaser/.claude/data/venv/bin/python3
"""
Stop Dispatcher - Consolidated Stop hooks.

Handlers:
- uncommitted_reminder: Check for uncommitted git changes
- auto_continue: Evaluate if Claude should continue working

Runs on Stop event to handle session ending.
"""
import json
import os
import subprocess
import time
from pathlib import Path

from hooks.dispatchers.base import SimpleDispatcher
from hooks.config import Timeouts, Thresholds, AutoContinue
from hooks.hook_utils import log_event, read_state, write_state


# =============================================================================
# Git Status (from uncommitted_reminder)
# =============================================================================

def get_git_status(cwd: str = None) -> dict:
    """Get git status for the working directory."""
    result = {
        "is_git_repo": False,
        "has_staged": False,
        "has_unstaged": False,
        "has_untracked": False,
        "branch": "",
        "ahead": 0,
        "file_count": 0,
    }

    try:
        check = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=5
        )
        if check.returncode != 0:
            return result

        result["is_git_repo"] = True

        branch = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=5
        )
        result["branch"] = branch.stdout.strip()

        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=5
        )

        if status.returncode == 0:
            lines = status.stdout.strip().split('\n') if status.stdout.strip() else []
            result["file_count"] = len(lines)

            for line in lines:
                if not line:
                    continue
                index = line[0] if len(line) > 0 else ' '
                worktree = line[1] if len(line) > 1 else ' '

                if index != ' ' and index != '?':
                    result["has_staged"] = True
                if worktree != ' ' and worktree != '?':
                    result["has_unstaged"] = True
                if index == '?' or worktree == '?':
                    result["has_untracked"] = True

        ahead = subprocess.run(
            ["git", "rev-list", "--count", "@{upstream}..HEAD"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=5
        )
        if ahead.returncode == 0:
            result["ahead"] = int(ahead.stdout.strip() or 0)

    except (subprocess.TimeoutExpired, subprocess.SubprocessError, ValueError):
        pass

    return result


def check_uncommitted_changes(ctx: dict) -> list[str]:
    """Check for uncommitted git changes. Returns list of messages."""
    cwd = ctx.get("cwd") or ctx.get("working_directory") or os.getcwd()
    status = get_git_status(cwd)

    if not status["is_git_repo"]:
        return []

    messages = []

    if status["has_staged"] or status["has_unstaged"]:
        msg_parts = []
        if status["has_staged"]:
            msg_parts.append("staged")
        if status["has_unstaged"]:
            msg_parts.append("unstaged")
        messages.append(f"Uncommitted changes ({', '.join(msg_parts)}) in {status['file_count']} files")

    if status["ahead"] > 0:
        messages.append(f"Branch '{status['branch']}' is {status['ahead']} commits ahead of remote (unpushed)")

    if status["has_untracked"] and status["file_count"] <= 10:
        messages.append("Untracked files present")

    return messages


# =============================================================================
# Auto-Continue (from auto_continue)
# =============================================================================

STATE_KEY = "auto-continue"
MAX_CONTINUATIONS = Thresholds.MAX_CONTINUATIONS
WINDOW_SECONDS = Timeouts.CONTINUE_WINDOW

# Use lazy-compiled patterns from config
def get_incomplete_patterns():
    return AutoContinue.get_incomplete()

def get_complete_patterns():
    return AutoContinue.get_complete()


def load_continue_state() -> dict:
    """Load rate limit state."""
    return read_state(STATE_KEY, {"continuations": [], "last_reset": time.time()})


def save_continue_state(state: dict):
    """Save rate limit state."""
    write_state(STATE_KEY, state)


def check_rate_limit() -> bool:
    """Check if we can continue (within rate limit)."""
    state = load_continue_state()
    now = time.time()

    window_start = now - WINDOW_SECONDS
    state["continuations"] = [t for t in state["continuations"] if t > window_start]

    if len(state["continuations"]) >= MAX_CONTINUATIONS:
        log_event("stop_handler", "rate_limited", {
            "count": len(state["continuations"]),
            "max": MAX_CONTINUATIONS
        })
        return False

    return True


def record_continuation():
    """Record that we triggered a continuation."""
    state = load_continue_state()
    state["continuations"].append(time.time())
    save_continue_state(state)


def extract_last_messages(ctx: dict, count: int = 10) -> list:
    """Extract last N messages from transcript context."""
    messages = ctx.get("messages", [])
    if messages:
        return messages[-count:]

    transcript_path = ctx.get("transcript_path", "")
    if not transcript_path:
        return []

    try:
        with open(transcript_path) as f:
            lines = f.readlines()[-count * 5:]
            messages = []
            for line in lines:
                try:
                    entry = json.loads(line)
                    if entry.get("type") in ("human", "assistant"):
                        messages.append(entry)
                except json.JSONDecodeError:
                    continue
            return messages[-count:]
    except (OSError, PermissionError):
        return []


def heuristic_should_continue(messages: list) -> tuple[bool, str]:
    """Use heuristics to check if work should continue."""
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
    """Check if work should auto-continue. Returns continue result or None."""
    if not check_rate_limit():
        return None

    messages = extract_last_messages(ctx)
    should_continue, reason = heuristic_should_continue(messages)

    log_event("stop_handler", "auto_continue_evaluated", {
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


# =============================================================================
# Combined Handler
# =============================================================================

def handle_stop(ctx: dict) -> tuple[list[str], dict | None]:
    """
    Handle Stop event.

    Returns:
        (messages, continue_result)
        - messages: List of warning messages to display
        - continue_result: Dict with "result": "continue" if should continue, else None
    """
    # Check for uncommitted changes
    uncommitted_messages = check_uncommitted_changes(ctx)

    # Check for auto-continue
    continue_result = check_auto_continue(ctx)

    return uncommitted_messages, continue_result


# =============================================================================
# Dispatcher
# =============================================================================

class StopDispatcher(SimpleDispatcher):
    """Stop event dispatcher with special output handling."""

    DISPATCHER_NAME = "stop_handler"
    EVENT_TYPE = "Stop"

    def __init__(self):
        super().__init__()
        self._continue_result = None

    def handle(self, ctx: dict) -> list[str]:
        messages, continue_result = handle_stop(ctx)
        self._continue_result = continue_result
        return messages

    def format_output(self, messages: list[str]) -> str | None:
        """Custom formatting for uncommitted changes + continue result."""
        output_parts = []

        # Format uncommitted change warnings
        if messages:
            output_parts.append("[Uncommitted Changes] Before ending session:")
            for msg in messages:
                output_parts.append(f"  - {msg}")
            if any("Uncommitted" in m for m in messages):
                output_parts.append("  Consider: git commit -m 'WIP: <description>'")
            if any("ahead" in m for m in messages):
                output_parts.append("  Consider: git push")

        # Add continue result as JSON
        if self._continue_result:
            output_parts.append(json.dumps(self._continue_result))

        return "\n".join(output_parts) if output_parts else None


if __name__ == "__main__":
    StopDispatcher().run()

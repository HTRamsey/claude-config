#!/home/jonglaser/.claude/data/venv/bin/python3
"""
SubagentLifecycle hook - tracks subagent lifecycle for metrics and timing.
Called via pre_tool_dispatcher (handle_start) and post_tool_dispatcher (handle_complete)
for Task tool invocations.

Also maintains Reflexion memory - a log of task outcomes and lessons
for learning from past subagent executions.
"""
import hashlib
import json
import sys
import os
from datetime import datetime
from pathlib import Path

from hook_utils import (
    graceful_main,
    read_stdin_context,
    log_event,
    get_session_state,
    update_session_state
)

REFLEXION_LOG = Path.home() / ".claude/data/reflexion-log.json"
MAX_REFLEXION_ENTRIES = 100  # Keep last N entries


def load_reflexion_log() -> list:
    """Load the reflexion log."""
    if REFLEXION_LOG.exists():
        try:
            with open(REFLEXION_LOG) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return []


def save_reflexion_log(entries: list):
    """Save the reflexion log, trimming old entries."""
    try:
        REFLEXION_LOG.parent.mkdir(parents=True, exist_ok=True)
        # Keep only last N entries
        trimmed = entries[-MAX_REFLEXION_ENTRIES:]
        with open(REFLEXION_LOG, "w") as f:
            json.dump(trimmed, f, indent=2)
    except IOError as e:
        log_event("subagent_lifecycle", "reflexion_save_error", {"error": str(e)})


def extract_task_summary(ctx: dict) -> str:
    """Extract a summary of the task from context."""
    tool_input = ctx.get("tool_input", {})
    # Try to get from prompt or description
    prompt = tool_input.get("prompt", ctx.get("prompt", ""))
    description = tool_input.get("description", ctx.get("description", ""))

    summary = description or prompt[:100]
    if len(prompt) > 100 and not description:
        summary += "..."
    return summary


def extract_outcome(ctx: dict) -> str:
    """Determine outcome from stop_reason and context."""
    stop_reason = ctx.get("stop_reason", "")

    if stop_reason == "completed":
        return "success"
    elif stop_reason in ("error", "failed"):
        return "failure"
    elif stop_reason == "interrupted":
        return "interrupted"
    else:
        return "unknown"


def extract_lessons(ctx: dict, outcome: str) -> list:
    """Extract lessons learned from the task output."""
    lessons = []
    output = ctx.get("tool_output", "") or ctx.get("output", "") or ctx.get("result", "")

    # For failures, try to extract what went wrong
    if outcome == "failure":
        if "timeout" in output.lower():
            lessons.append("Task timed out - consider breaking into smaller parts")
        if "not found" in output.lower():
            lessons.append("File or resource not found - verify paths before dispatching")
        if "permission" in output.lower():
            lessons.append("Permission issue - check access rights")

    # For successes, note patterns
    if outcome == "success":
        if "test" in output.lower() and "pass" in output.lower():
            lessons.append("Tests passed - approach validated")
        if "refactor" in output.lower():
            lessons.append("Refactoring completed successfully")

    return lessons


def record_reflexion(ctx: dict, duration_s: float | None):
    """Record a reflexion entry for this subagent completion."""
    tool_input = ctx.get("tool_input", {})
    subagent_type = tool_input.get("subagent_type", ctx.get("subagent_type", "unknown"))
    prompt = tool_input.get("prompt", ctx.get("prompt", ""))

    # Create a hash of the task for deduplication
    task_hash = hashlib.md5(
        f"{subagent_type}:{prompt[:200]}".encode()
    ).hexdigest()[:12]

    outcome = extract_outcome(ctx)
    lessons = extract_lessons(ctx, outcome)

    entry = {
        "task_hash": task_hash,
        "subagent_type": subagent_type,
        "task_summary": extract_task_summary(ctx),
        "outcome": outcome,
        "lessons": lessons,
        "duration_s": duration_s,
        "timestamp": datetime.now().isoformat()
    }

    # Only record if there's meaningful content
    if entry["task_summary"] or lessons:
        log = load_reflexion_log()
        log.append(entry)
        save_reflexion_log(log)

        log_event("subagent_lifecycle", "reflexion_recorded", {
            "task_hash": task_hash,
            "outcome": outcome,
            "lesson_count": len(lessons)
        })


def handle_start(ctx):
    """Handle Task tool PreToolUse - track spawn time and counts."""
    tool_input = ctx.get("tool_input", {})
    subagent_type = tool_input.get("subagent_type", ctx.get("subagent_type", "unknown"))
    subagent_id = ctx.get("subagent_id", ctx.get("tool_use_id", ""))

    state = get_session_state()

    # Track active subagents with their start times
    active_subagents = state.get("active_subagents", {})
    active_subagents[subagent_id] = {
        "type": subagent_type,
        "started_at": datetime.now().isoformat()
    }

    # Track spawn counts per type
    spawn_counts = state.get("subagent_spawn_counts", {})
    spawn_counts[subagent_type] = spawn_counts.get(subagent_type, 0) + 1

    update_session_state({
        "active_subagents": active_subagents,
        "subagent_spawn_counts": spawn_counts
    })

    log_event("subagent_start", "success", {
        "subagent_type": subagent_type,
        "subagent_id": subagent_id,
        "spawn_count": spawn_counts[subagent_type]
    })


def handle_complete(ctx):
    """Handle Task tool PostToolUse - track completion and calculate duration."""
    tool_input = ctx.get("tool_input", {})
    subagent_type = tool_input.get("subagent_type", ctx.get("subagent_type", "unknown"))
    subagent_id = ctx.get("subagent_id", ctx.get("tool_use_id", ""))
    stop_reason = ctx.get("stop_reason", "completed" if not ctx.get("tool_error") else "error")

    state = get_session_state()
    subagent_stats = state.get("subagent_stats", {})

    if subagent_type not in subagent_stats:
        subagent_stats[subagent_type] = {"count": 0, "last_run": None, "total_duration_s": 0}

    subagent_stats[subagent_type]["count"] += 1
    subagent_stats[subagent_type]["last_run"] = datetime.now().isoformat()

    # Calculate duration if we have start time from SubagentStart hook
    duration_s = None
    active_subagents = state.get("active_subagents", {})
    if subagent_id in active_subagents:
        try:
            started_at = datetime.fromisoformat(active_subagents[subagent_id]["started_at"])
            duration_s = (datetime.now() - started_at).total_seconds()
            subagent_stats[subagent_type]["total_duration_s"] = \
                subagent_stats[subagent_type].get("total_duration_s", 0) + duration_s
        except (ValueError, KeyError):
            pass
        # Clean up active subagent entry
        del active_subagents[subagent_id]

    update_session_state({
        "subagent_stats": subagent_stats,
        "active_subagents": active_subagents
    })

    log_event("subagent_complete", "success", {
        "subagent_type": subagent_type,
        "subagent_id": subagent_id,
        "stop_reason": stop_reason,
        "duration_s": duration_s,
        "total_runs": subagent_stats[subagent_type]["count"]
    })

    # Record to Reflexion memory
    record_reflexion(ctx, duration_s)


@graceful_main("subagent_lifecycle")
def main():
    ctx = read_stdin_context()

    # Detect event type from context
    event_type = ctx.get("event", "")

    if event_type == "SubagentStart":
        handle_start(ctx)
    elif event_type == "SubagentStop":
        handle_complete(ctx)
    else:
        # Fallback: check for stop_reason to distinguish events
        if "stop_reason" in ctx:
            handle_complete(ctx)
        else:
            handle_start(ctx)


if __name__ == "__main__":
    main()
    sys.exit(0)

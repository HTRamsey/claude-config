#!/home/jonglaser/.claude/venv/bin/python3
"""
SubagentLifecycle hook - tracks subagent lifecycle for metrics and timing.
Handles both SubagentStart and SubagentStop events.
"""
import sys
import os
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hook_utils import (
    graceful_main,
    read_stdin_context,
    log_event,
    get_session_state,
    update_session_state
)


def handle_start(ctx):
    """Handle SubagentStart event - track spawn time and counts."""
    subagent_type = ctx.get("subagent_type", "unknown")
    subagent_id = ctx.get("subagent_id", "")

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
    """Handle SubagentStop event - track completion and calculate duration."""
    subagent_type = ctx.get("subagent_type", "unknown")
    subagent_id = ctx.get("subagent_id", "")
    stop_reason = ctx.get("stop_reason", "")

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

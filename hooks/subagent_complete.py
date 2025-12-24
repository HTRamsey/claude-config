#!/home/jonglaser/.claude/venv/bin/python3
"""
SubagentStop hook - tracks subagent completion for metrics and debugging.
"""
import sys
import os
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from hook_utils import (
        graceful_main,
        read_stdin_context,
        log_event,
        get_session_state,
        update_session_state
    )
except ImportError:
    def graceful_main(name):
        def decorator(func):
            return func
        return decorator
    def read_stdin_context():
        import json
        try:
            return json.load(sys.stdin)
        except:
            return {}
    def log_event(*args, **kwargs):
        pass
    def get_session_state():
        return {}
    def update_session_state(*args, **kwargs):
        pass


@graceful_main("subagent_complete")
def main():
    ctx = read_stdin_context()

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


if __name__ == "__main__":
    main()
    sys.exit(0)

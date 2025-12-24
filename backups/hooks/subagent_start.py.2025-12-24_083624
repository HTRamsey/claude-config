#!/home/jonglaser/.claude/venv/bin/python3
"""
SubagentStart hook - tracks subagent spawns for metrics and timing.
Records start time so SubagentStop can calculate duration.
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


@graceful_main("subagent_start")
def main():
    ctx = read_stdin_context()

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


if __name__ == "__main__":
    main()
    sys.exit(0)

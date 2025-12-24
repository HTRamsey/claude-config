#!/home/jonglaser/.claude/venv/bin/python3
"""
PreCompact hook - saves context before automatic compaction.
Backs up transcript and logs key session state.
"""
import sys
import os
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from hook_utils import (
        graceful_main,
        read_stdin_context,
        backup_transcript,
        log_event,
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
    def backup_transcript(*args, **kwargs):
        return None
    def log_event(*args, **kwargs):
        pass
    def update_session_state(*args, **kwargs):
        pass


@graceful_main("precompact_save")
def main():
    ctx = read_stdin_context()
    transcript_path = ctx.get("transcript_path", "")

    if not transcript_path:
        return

    backup_path = backup_transcript(transcript_path, reason="pre_compact")

    if backup_path:
        update_session_state({
            "last_compact_backup": backup_path,
            "last_compact_time": datetime.now().isoformat()
        })
        log_event("precompact_save", "success", {
            "backup_path": backup_path
        })


if __name__ == "__main__":
    main()
    sys.exit(0)

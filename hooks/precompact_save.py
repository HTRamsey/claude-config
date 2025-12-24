#!/home/jonglaser/.claude/venv/bin/python3
"""
PreCompact hook - saves context before automatic compaction.
Backs up transcript and logs key session state.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hook_utils import (
    graceful_main,
    read_stdin_context,
    backup_transcript,
    log_event,
    update_session_state
)
from datetime import datetime


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

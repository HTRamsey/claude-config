"""
Transcript backup utilities.
"""
import os
from datetime import datetime
from pathlib import Path

from .io import file_lock
from .logging import log_event, DATA_DIR
from .session import get_session_id


def backup_transcript(transcript_path: str, reason: str = "manual", ctx: dict = None) -> str:
    """
    Backup transcript to data directory.

    Args:
        transcript_path: Path to transcript file
        reason: Reason for backup (pre_compact, checkpoint, etc.)
        ctx: Context dict (optional, for session ID)

    Returns:
        Path to backup file, or empty string on failure
    """
    try:
        if not transcript_path or not os.path.exists(transcript_path):
            return ""

        DATA_DIR.mkdir(parents=True, exist_ok=True)
        backup_dir = DATA_DIR / "transcript-backups"
        backup_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        session_id = get_session_id(ctx, transcript_path)
        backup_name = f"{session_id}-{reason}-{timestamp}.jsonl"
        backup_path = backup_dir / backup_name

        with open(transcript_path, 'rb') as src:
            with open(backup_path, 'wb') as dst:
                with file_lock(dst):
                    dst.write(src.read())

        log_event("backup", "success", {
            "reason": reason,
            "path": str(backup_path),
            "size": os.path.getsize(backup_path)
        })

        # Clean old backups (keep last 20)
        backups = sorted(backup_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime)
        for old_backup in backups[:-20]:
            old_backup.unlink()

        return str(backup_path)
    except Exception as e:
        log_event("backup", "error", {"reason": reason, "error": str(e)}, "error")
        return ""

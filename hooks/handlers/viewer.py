"""
Viewer handler - session viewer daemon management.

Provides viewer process checking and launching for session_start dispatcher.
"""
import os
import subprocess
import time
from pathlib import Path


VIEWER_SCRIPT = Path.home() / ".claude" / "scripts" / "diagnostics" / "session-viewer.py"
DATA_DIR = Path.home() / ".claude" / "data"
PID_FILE = DATA_DIR / "session-viewer.pid"
DEFAULT_PORT = 5111


def is_viewer_running() -> bool:
    """Check if viewer process is running.

    Returns:
        True if viewer is running, False otherwise.
    """
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
            os.kill(pid, 0)  # Check if process exists
            return True
        except (ValueError, ProcessLookupError, PermissionError):
            PID_FILE.unlink(missing_ok=True)
    return False


def start_viewer() -> str | None:
    """Start the session viewer in background.

    Returns:
        Status message with URL, or None on failure.
    """
    if not VIEWER_SCRIPT.exists():
        return None

    try:
        subprocess.Popen(
            [str(VIEWER_SCRIPT), "--daemon", "start"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return f"Session viewer: http://localhost:{DEFAULT_PORT}"
    except Exception:
        return None


def maybe_start_viewer() -> str | None:
    """Start viewer if not already running (rate-limited).

    Only checks once per minute to avoid startup spam.

    Returns:
        Status message if viewer was started, None otherwise.
    """
    session_marker = DATA_DIR / ".viewer_checked"
    now = time.time()

    # Rate limit: only check once per minute
    if session_marker.exists():
        try:
            last_check = float(session_marker.read_text().strip())
            if now - last_check < 60:
                return None
        except (ValueError, OSError):
            pass

    # Update check timestamp
    try:
        session_marker.write_text(str(now))
    except OSError:
        pass

    if is_viewer_running():
        return None

    return start_viewer()

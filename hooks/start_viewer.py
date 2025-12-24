#!/home/jonglaser/.claude/venv/bin/python3
"""Start claude-code-viewer if not already running.

UserPromptSubmit hook - checks on first prompt of session.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

# Import shared utilities
sys.path.insert(0, str(Path(__file__).parent))
try:
    from hook_utils import graceful_main, log_event
    HAS_UTILS = True
except ImportError:
    HAS_UTILS = False
    def graceful_main(name):
        def decorator(func):
            return func
        return decorator
    def log_event(*args, **kwargs):
        pass

VIEWER_CMD = "claude-code-viewer"
PID_FILE = Path.home() / ".claude" / ".viewer.pid"
DEFAULT_PORT = 3000


def is_viewer_running() -> bool:
    """Check if viewer process is running."""
    # Check PID file first
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
            # Check if process exists
            os.kill(pid, 0)
            return True
        except (ValueError, ProcessLookupError, PermissionError):
            # PID file stale, remove it
            PID_FILE.unlink(missing_ok=True)

    # Fallback: check if port is in use
    try:
        result = subprocess.run(
            ["lsof", "-i", f":{DEFAULT_PORT}", "-t"],
            capture_output=True,
            text=True,
            timeout=2
        )
        return bool(result.stdout.strip())
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    # Fallback: pgrep
    try:
        result = subprocess.run(
            ["pgrep", "-f", VIEWER_CMD],
            capture_output=True,
            text=True,
            timeout=2
        )
        return bool(result.stdout.strip())
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return False


def start_viewer() -> bool:
    """Start the viewer in background."""
    try:
        # Start in background, detached from terminal
        process = subprocess.Popen(
            [VIEWER_CMD],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )

        # Save PID
        PID_FILE.parent.mkdir(parents=True, exist_ok=True)
        PID_FILE.write_text(str(process.pid))

        # Wait briefly for server to start, then open browser
        import time
        time.sleep(1)
        subprocess.Popen(
            ["firefox", f"http://localhost:{DEFAULT_PORT}"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )

        return True
    except FileNotFoundError:
        return False
    except Exception:
        return False


@graceful_main("start_viewer")
def main():
    # Only run once per session - use a session marker
    session_marker = Path.home() / ".claude" / ".viewer_checked"

    # Get current session ID from environment or create marker with timestamp
    # Simple approach: check if we've run in the last 5 seconds (same session)
    import time
    now = time.time()

    if session_marker.exists():
        try:
            last_check = float(session_marker.read_text().strip())
            # If checked within last 60 seconds, skip (same session)
            if now - last_check < 60:
                sys.exit(0)
        except (ValueError, OSError):
            pass

    # Mark as checked
    session_marker.write_text(str(now))

    if is_viewer_running():
        sys.exit(0)

    if start_viewer():
        # Notify user
        print(json.dumps({
            "message": f"Started claude-code-viewer on http://localhost:{DEFAULT_PORT}"
        }))

    sys.exit(0)


if __name__ == "__main__":
    main()

"""
Cross-platform notification abstraction.

Supports Linux (notify-send), macOS (osascript), and Windows (powershell).
Falls back gracefully if notification system unavailable.

Security: All user input is properly escaped to prevent command injection.
"""
import shutil
import subprocess
import sys
from typing import Literal


def _escape_applescript(text: str) -> str:
    """Escape text for AppleScript string literals.

    AppleScript uses backslash escaping for special characters.
    """
    return text.replace("\\", "\\\\").replace('"', '\\"')


def _escape_powershell(text: str) -> str:
    """Escape text for PowerShell string literals.

    PowerShell uses backtick for escaping in double-quoted strings.
    """
    return text.replace("`", "``").replace('"', '`"').replace("$", "`$")

Urgency = Literal["low", "normal", "critical"]


def _get_platform() -> str:
    """Detect platform."""
    if sys.platform == "darwin":
        return "macos"
    elif sys.platform == "win32":
        return "windows"
    return "linux"


def _notify_linux(title: str, body: str, urgency: Urgency) -> bool:
    """Send notification via notify-send (Linux)."""
    if not shutil.which("notify-send"):
        return False
    try:
        subprocess.Popen(
            [
                "notify-send",
                "--app-name=Claude Code",
                f"--urgency={urgency}",
                title,
                body,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except Exception:
        return False


def _notify_macos(title: str, body: str, urgency: Urgency) -> bool:
    """Send notification via osascript (macOS).

    Security: Title and body are escaped to prevent AppleScript injection.
    """
    if not shutil.which("osascript"):
        return False
    try:
        safe_title = _escape_applescript(title)
        safe_body = _escape_applescript(body)
        script = f'display notification "{safe_body}" with title "{safe_title}"'
        subprocess.Popen(
            ["osascript", "-e", script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except Exception:
        return False


def _notify_windows(title: str, body: str, urgency: Urgency) -> bool:
    """Send notification via PowerShell (Windows 10+).

    Security: Title and body are escaped to prevent PowerShell injection.
    """
    if not shutil.which("powershell"):
        return False
    try:
        safe_title = _escape_powershell(title)
        safe_body = _escape_powershell(body)
        # Windows toast notification via PowerShell
        script = f'''
        [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
        $template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
        $textNodes = $template.GetElementsByTagName("text")
        $textNodes.Item(0).AppendChild($template.CreateTextNode("{safe_title}")) | Out-Null
        $textNodes.Item(1).AppendChild($template.CreateTextNode("{safe_body}")) | Out-Null
        $toast = [Windows.UI.Notifications.ToastNotification]::new($template)
        [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("Claude Code").Show($toast)
        '''
        subprocess.Popen(
            ["powershell", "-Command", script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except Exception:
        return False


def send_notification(
    title: str,
    body: str,
    urgency: Urgency = "normal"
) -> bool:
    """
    Send a desktop notification (cross-platform).

    Args:
        title: Notification title
        body: Notification body text
        urgency: Urgency level ("low", "normal", "critical")

    Returns:
        True if notification was sent, False if unavailable

    Example:
        send_notification("Build Complete", "All tests passed!", urgency="normal")
        send_notification("Build Failed", "3 errors found", urgency="critical")
    """
    platform = _get_platform()

    if platform == "linux":
        return _notify_linux(title, body, urgency)
    elif platform == "macos":
        return _notify_macos(title, body, urgency)
    elif platform == "windows":
        return _notify_windows(title, body, urgency)

    return False


def is_notification_available() -> bool:
    """Check if desktop notifications are available on this system."""
    platform = _get_platform()

    if platform == "linux":
        return shutil.which("notify-send") is not None
    elif platform == "macos":
        return shutil.which("osascript") is not None
    elif platform == "windows":
        return shutil.which("powershell") is not None

    return False

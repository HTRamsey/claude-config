#!/usr/bin/env python3
"""Unit tests for notify.py - cross-platform notification abstraction.

Tests escaping functions, platform detection, and notification dispatch.
"""

import sys
from unittest import TestCase, main
from unittest.mock import patch, MagicMock

from hooks.hook_utils.notify import (
    _escape_applescript,
    _escape_powershell,
    _get_platform,
    _notify_linux,
    _notify_macos,
    _notify_windows,
    send_notification,
    is_notification_available,
)


class TestEscapeApplescript(TestCase):
    """Tests for AppleScript string escaping."""

    def test_escapes_backslash(self):
        """Backslashes are doubled."""
        result = _escape_applescript("path\\to\\file")
        self.assertEqual(result, "path\\\\to\\\\file")

    def test_escapes_double_quote(self):
        """Double quotes are escaped."""
        result = _escape_applescript('Say "hello"')
        self.assertEqual(result, 'Say \\"hello\\"')

    def test_combined_escaping(self):
        """Both backslashes and quotes are escaped."""
        result = _escape_applescript('File: "C:\\test"')
        self.assertEqual(result, 'File: \\"C:\\\\test\\"')

    def test_normal_text_unchanged(self):
        """Normal text passes through unchanged."""
        result = _escape_applescript("Hello World")
        self.assertEqual(result, "Hello World")

    def test_empty_string(self):
        """Empty string returns empty."""
        result = _escape_applescript("")
        self.assertEqual(result, "")


class TestEscapePowershell(TestCase):
    """Tests for PowerShell string escaping."""

    def test_escapes_backtick(self):
        """Backticks are doubled."""
        result = _escape_powershell("test`value")
        self.assertEqual(result, "test``value")

    def test_escapes_double_quote(self):
        """Double quotes are backtick-escaped."""
        result = _escape_powershell('Say "hello"')
        self.assertEqual(result, 'Say `"hello`"')

    def test_escapes_dollar_sign(self):
        """Dollar signs are backtick-escaped."""
        result = _escape_powershell("Cost is $100")
        self.assertEqual(result, "Cost is `$100")

    def test_combined_escaping(self):
        """Multiple special characters are all escaped."""
        result = _escape_powershell('$var = "test`"')
        self.assertEqual(result, '`$var = `"test```"')

    def test_normal_text_unchanged(self):
        """Normal text passes through unchanged."""
        result = _escape_powershell("Hello World")
        self.assertEqual(result, "Hello World")


class TestGetPlatform(TestCase):
    """Tests for platform detection."""

    def test_darwin_returns_macos(self):
        """Darwin platform returns 'macos'."""
        with patch.object(sys, "platform", "darwin"):
            result = _get_platform()
            self.assertEqual(result, "macos")

    def test_win32_returns_windows(self):
        """Win32 platform returns 'windows'."""
        with patch.object(sys, "platform", "win32"):
            result = _get_platform()
            self.assertEqual(result, "windows")

    def test_linux_returns_linux(self):
        """Linux platform returns 'linux'."""
        with patch.object(sys, "platform", "linux"):
            result = _get_platform()
            self.assertEqual(result, "linux")

    def test_unknown_returns_linux(self):
        """Unknown platform defaults to 'linux'."""
        with patch.object(sys, "platform", "freebsd"):
            result = _get_platform()
            self.assertEqual(result, "linux")


class TestNotifyLinux(TestCase):
    """Tests for Linux notification via notify-send."""

    @patch("shutil.which")
    def test_returns_false_if_notify_send_not_found(self, mock_which):
        """Returns False if notify-send not installed."""
        mock_which.return_value = None
        result = _notify_linux("Title", "Body", "normal")
        self.assertFalse(result)

    @patch("shutil.which")
    @patch("subprocess.Popen")
    def test_calls_notify_send_with_correct_args(self, mock_popen, mock_which):
        """Calls notify-send with correct arguments."""
        mock_which.return_value = "/usr/bin/notify-send"
        result = _notify_linux("Test Title", "Test Body", "critical")

        self.assertTrue(result)
        mock_popen.assert_called_once()
        args = mock_popen.call_args[0][0]
        self.assertEqual(args[0], "notify-send")
        self.assertIn("--app-name=Claude Code", args)
        self.assertIn("--urgency=critical", args)
        self.assertIn("Test Title", args)
        self.assertIn("Test Body", args)

    @patch("shutil.which")
    @patch("subprocess.Popen")
    def test_returns_false_on_exception(self, mock_popen, mock_which):
        """Returns False if Popen raises exception."""
        mock_which.return_value = "/usr/bin/notify-send"
        mock_popen.side_effect = OSError("Failed")
        result = _notify_linux("Title", "Body", "normal")
        self.assertFalse(result)


class TestNotifyMacos(TestCase):
    """Tests for macOS notification via osascript."""

    @patch("shutil.which")
    def test_returns_false_if_osascript_not_found(self, mock_which):
        """Returns False if osascript not found."""
        mock_which.return_value = None
        result = _notify_macos("Title", "Body", "normal")
        self.assertFalse(result)

    @patch("shutil.which")
    @patch("subprocess.Popen")
    def test_escapes_title_and_body(self, mock_popen, mock_which):
        """Title and body are escaped for AppleScript safety."""
        mock_which.return_value = "/usr/bin/osascript"
        result = _notify_macos('Say "hello"', 'Path: C:\\test', "normal")

        self.assertTrue(result)
        args = mock_popen.call_args[0][0]
        # Script should contain escaped versions
        script = args[2]  # osascript -e <script>
        self.assertIn('\\"', script)  # Escaped quotes
        self.assertIn('\\\\', script)  # Escaped backslash

    @patch("shutil.which")
    @patch("subprocess.Popen")
    def test_returns_false_on_exception(self, mock_popen, mock_which):
        """Returns False if Popen raises exception."""
        mock_which.return_value = "/usr/bin/osascript"
        mock_popen.side_effect = OSError("Failed")
        result = _notify_macos("Title", "Body", "normal")
        self.assertFalse(result)


class TestNotifyWindows(TestCase):
    """Tests for Windows notification via PowerShell."""

    @patch("shutil.which")
    def test_returns_false_if_powershell_not_found(self, mock_which):
        """Returns False if powershell not found."""
        mock_which.return_value = None
        result = _notify_windows("Title", "Body", "normal")
        self.assertFalse(result)

    @patch("shutil.which")
    @patch("subprocess.Popen")
    def test_escapes_title_and_body(self, mock_popen, mock_which):
        """Title and body are escaped for PowerShell safety."""
        mock_which.return_value = "/usr/bin/powershell"
        result = _notify_windows('Cost: $100', 'Say "hi"', "normal")

        self.assertTrue(result)
        args = mock_popen.call_args[0][0]
        script = args[2]  # powershell -Command <script>
        self.assertIn('`$', script)  # Escaped dollar
        self.assertIn('`"', script)  # Escaped quote

    @patch("shutil.which")
    @patch("subprocess.Popen")
    def test_returns_false_on_exception(self, mock_popen, mock_which):
        """Returns False if Popen raises exception."""
        mock_which.return_value = "/usr/bin/powershell"
        mock_popen.side_effect = OSError("Failed")
        result = _notify_windows("Title", "Body", "normal")
        self.assertFalse(result)


class TestSendNotification(TestCase):
    """Tests for unified send_notification function."""

    @patch("hooks.hook_utils.notify._get_platform")
    @patch("hooks.hook_utils.notify._notify_linux")
    def test_dispatches_to_linux(self, mock_notify, mock_platform):
        """Dispatches to Linux handler on Linux platform."""
        mock_platform.return_value = "linux"
        mock_notify.return_value = True

        result = send_notification("Title", "Body", "normal")

        self.assertTrue(result)
        mock_notify.assert_called_once_with("Title", "Body", "normal")

    @patch("hooks.hook_utils.notify._get_platform")
    @patch("hooks.hook_utils.notify._notify_macos")
    def test_dispatches_to_macos(self, mock_notify, mock_platform):
        """Dispatches to macOS handler on Darwin platform."""
        mock_platform.return_value = "macos"
        mock_notify.return_value = True

        result = send_notification("Title", "Body", "critical")

        self.assertTrue(result)
        mock_notify.assert_called_once_with("Title", "Body", "critical")

    @patch("hooks.hook_utils.notify._get_platform")
    @patch("hooks.hook_utils.notify._notify_windows")
    def test_dispatches_to_windows(self, mock_notify, mock_platform):
        """Dispatches to Windows handler on Win32 platform."""
        mock_platform.return_value = "windows"
        mock_notify.return_value = True

        result = send_notification("Title", "Body", "low")

        self.assertTrue(result)
        mock_notify.assert_called_once_with("Title", "Body", "low")

    @patch("hooks.hook_utils.notify._get_platform")
    def test_returns_false_for_unknown_platform(self, mock_platform):
        """Returns False for unknown platform."""
        mock_platform.return_value = "unknown"
        result = send_notification("Title", "Body")
        self.assertFalse(result)

    @patch("hooks.hook_utils.notify._get_platform")
    @patch("hooks.hook_utils.notify._notify_linux")
    def test_default_urgency_is_normal(self, mock_notify, mock_platform):
        """Default urgency is 'normal'."""
        mock_platform.return_value = "linux"
        mock_notify.return_value = True

        send_notification("Title", "Body")

        mock_notify.assert_called_once_with("Title", "Body", "normal")


class TestIsNotificationAvailable(TestCase):
    """Tests for is_notification_available function."""

    @patch("hooks.hook_utils.notify._get_platform")
    @patch("shutil.which")
    def test_linux_checks_notify_send(self, mock_which, mock_platform):
        """Linux checks for notify-send."""
        mock_platform.return_value = "linux"
        mock_which.return_value = "/usr/bin/notify-send"

        result = is_notification_available()

        self.assertTrue(result)
        mock_which.assert_called_with("notify-send")

    @patch("hooks.hook_utils.notify._get_platform")
    @patch("shutil.which")
    def test_macos_checks_osascript(self, mock_which, mock_platform):
        """macOS checks for osascript."""
        mock_platform.return_value = "macos"
        mock_which.return_value = "/usr/bin/osascript"

        result = is_notification_available()

        self.assertTrue(result)
        mock_which.assert_called_with("osascript")

    @patch("hooks.hook_utils.notify._get_platform")
    @patch("shutil.which")
    def test_windows_checks_powershell(self, mock_which, mock_platform):
        """Windows checks for powershell."""
        mock_platform.return_value = "windows"
        mock_which.return_value = "C:\\Windows\\powershell.exe"

        result = is_notification_available()

        self.assertTrue(result)
        mock_which.assert_called_with("powershell")

    @patch("hooks.hook_utils.notify._get_platform")
    @patch("shutil.which")
    def test_returns_false_when_tool_not_found(self, mock_which, mock_platform):
        """Returns False when required tool not found."""
        mock_platform.return_value = "linux"
        mock_which.return_value = None

        result = is_notification_available()

        self.assertFalse(result)

    @patch("hooks.hook_utils.notify._get_platform")
    def test_returns_false_for_unknown_platform(self, mock_platform):
        """Returns False for unknown platform."""
        mock_platform.return_value = "unknown"
        result = is_notification_available()
        self.assertFalse(result)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Unit tests for notify_complete.py - desktop notifications for long commands.

Tests the PostToolUse handler that sends notifications for Bash commands
that exceed the duration threshold.
"""

from unittest import TestCase, main
from unittest.mock import patch

from hooks.handlers.notify_complete import notify_complete
from hooks.config import Thresholds


class TestNotifyComplete(TestCase):
    """Tests for notify_complete PostToolUse handler."""

    def test_ignores_non_bash_tools(self):
        """Returns None for non-Bash tools."""
        raw = {
            "tool_name": "Read",
            "tool_input": {"file_path": "test.txt"},
            "tool_result": {"content": "test"},
            "duration_ms": 60000,  # 60 seconds
        }
        result = notify_complete(raw)
        self.assertIsNone(result)

    def test_ignores_short_commands(self):
        """Returns None for commands under threshold."""
        raw = {
            "tool_name": "Bash",
            "tool_input": {"command": "ls"},
            "tool_result": {"exit_code": 0, "output": "files"},
            "duration_ms": 1000,  # 1 second (under threshold)
        }
        result = notify_complete(raw)
        self.assertIsNone(result)

    @patch("hooks.handlers.notify_complete.is_notification_available")
    def test_skips_when_notifications_unavailable(self, mock_available):
        """Returns None if notifications are not available."""
        mock_available.return_value = False
        raw = {
            "tool_name": "Bash",
            "tool_input": {"command": "make build"},
            "tool_result": {"exit_code": 0, "output": "done"},
            "duration_ms": Thresholds.min_notify_duration * 1000 + 1000,
        }
        result = notify_complete(raw)
        self.assertIsNone(result)

    @patch("hooks.handlers.notify_complete.is_notification_available")
    @patch("hooks.handlers.notify_complete.send_notification")
    def test_sends_success_notification(self, mock_send, mock_available):
        """Sends normal urgency notification for successful commands."""
        mock_available.return_value = True
        duration_ms = Thresholds.min_notify_duration * 1000 + 5000  # threshold + 5s
        raw = {
            "tool_name": "Bash",
            "tool_input": {"command": "npm run build"},
            "tool_result": {"exit_code": 0, "output": "Built successfully"},
            "duration_ms": duration_ms,
        }
        result = notify_complete(raw)

        self.assertIsNone(result)  # Handler returns None after sending
        mock_send.assert_called_once()
        title, message, urgency = mock_send.call_args[0][0], mock_send.call_args[0][1], mock_send.call_args[1]["urgency"]
        self.assertIn("Complete", title)
        self.assertIn("✓", title)
        self.assertEqual(urgency, "normal")

    @patch("hooks.handlers.notify_complete.is_notification_available")
    @patch("hooks.handlers.notify_complete.send_notification")
    def test_sends_failure_notification(self, mock_send, mock_available):
        """Sends critical urgency notification for failed commands."""
        mock_available.return_value = True
        duration_ms = Thresholds.min_notify_duration * 1000 + 5000
        raw = {
            "tool_name": "Bash",
            "tool_input": {"command": "pytest tests/"},
            "tool_result": {"exit_code": 1, "output": "3 failed"},
            "duration_ms": duration_ms,
        }
        result = notify_complete(raw)

        self.assertIsNone(result)
        mock_send.assert_called_once()
        title, message, urgency = mock_send.call_args[0][0], mock_send.call_args[0][1], mock_send.call_args[1]["urgency"]
        self.assertIn("Failed", title)
        self.assertIn("✗", title)
        self.assertEqual(urgency, "critical")

    @patch("hooks.handlers.notify_complete.is_notification_available")
    @patch("hooks.handlers.notify_complete.send_notification")
    def test_truncates_long_commands(self, mock_send, mock_available):
        """Long commands are truncated to 50 characters."""
        mock_available.return_value = True
        long_command = "x" * 100
        duration_ms = Thresholds.min_notify_duration * 1000 + 5000
        raw = {
            "tool_name": "Bash",
            "tool_input": {"command": long_command},
            "tool_result": {"exit_code": 0},
            "duration_ms": duration_ms,
        }
        notify_complete(raw)

        message = mock_send.call_args[0][1]
        # Command part should be truncated
        self.assertIn("...", message)
        # Should not contain full 100-char command
        self.assertNotIn("x" * 100, message)

    @patch("hooks.handlers.notify_complete.is_notification_available")
    @patch("hooks.handlers.notify_complete.send_notification")
    def test_includes_duration_in_message(self, mock_send, mock_available):
        """Notification message includes duration."""
        mock_available.return_value = True
        duration_ms = 45000  # 45 seconds
        raw = {
            "tool_name": "Bash",
            "tool_input": {"command": "make test"},
            "tool_result": {"exit_code": 0},
            "duration_ms": duration_ms,
        }
        notify_complete(raw)

        message = mock_send.call_args[0][1]
        self.assertIn("45s", message)

    def test_handles_missing_tool_input(self):
        """Handles missing tool_input gracefully."""
        raw = {
            "tool_name": "Bash",
            "tool_result": {"exit_code": 0},
            "duration_ms": 1000,
        }
        result = notify_complete(raw)
        self.assertIsNone(result)  # Should not crash

    def test_handles_missing_duration(self):
        """Handles missing duration_ms gracefully."""
        raw = {
            "tool_name": "Bash",
            "tool_input": {"command": "ls"},
            "tool_result": {"exit_code": 0},
        }
        result = notify_complete(raw)
        self.assertIsNone(result)  # 0 duration = under threshold

    @patch("hooks.handlers.notify_complete.is_notification_available")
    @patch("hooks.handlers.notify_complete.send_notification")
    def test_handles_tool_response_key(self, mock_send, mock_available):
        """Handles both tool_response and tool_result keys."""
        mock_available.return_value = True
        duration_ms = Thresholds.min_notify_duration * 1000 + 5000
        raw = {
            "tool_name": "Bash",
            "tool_input": {"command": "npm test"},
            "tool_response": {"exit_code": 0},  # Alternative key
            "duration_ms": duration_ms,
        }
        notify_complete(raw)
        mock_send.assert_called_once()

    @patch("hooks.handlers.notify_complete.is_notification_available")
    @patch("hooks.handlers.notify_complete.send_notification")
    def test_handles_missing_exit_code(self, mock_send, mock_available):
        """Assumes exit_code=0 when not present."""
        mock_available.return_value = True
        duration_ms = Thresholds.min_notify_duration * 1000 + 5000
        raw = {
            "tool_name": "Bash",
            "tool_input": {"command": "npm test"},
            "tool_result": {},  # No exit_code
            "duration_ms": duration_ms,
        }
        notify_complete(raw)

        title = mock_send.call_args[0][0]
        self.assertIn("Complete", title)  # Treated as success

    def test_exact_threshold_boundary(self):
        """Command at exactly threshold duration triggers notification."""
        with patch("hooks.handlers.notify_complete.is_notification_available") as mock_avail, \
             patch("hooks.handlers.notify_complete.send_notification") as mock_send:
            mock_avail.return_value = True
            # Exactly at threshold - DOES trigger (>= via < check)
            raw = {
                "tool_name": "Bash",
                "tool_input": {"command": "npm test"},
                "tool_result": {"exit_code": 0},
                "duration_ms": Thresholds.min_notify_duration * 1000,
            }
            notify_complete(raw)
            mock_send.assert_called_once()

    def test_one_second_under_threshold(self):
        """Command 1 second under threshold does NOT trigger notification."""
        with patch("hooks.handlers.notify_complete.is_notification_available") as mock_avail, \
             patch("hooks.handlers.notify_complete.send_notification") as mock_send:
            mock_avail.return_value = True
            raw = {
                "tool_name": "Bash",
                "tool_input": {"command": "npm test"},
                "tool_result": {"exit_code": 0},
                "duration_ms": (Thresholds.min_notify_duration - 1) * 1000,
            }
            notify_complete(raw)
            mock_send.assert_not_called()

    def test_one_second_over_threshold(self):
        """Command 1 second over threshold triggers notification."""
        with patch("hooks.handlers.notify_complete.is_notification_available") as mock_avail, \
             patch("hooks.handlers.notify_complete.send_notification") as mock_send:
            mock_avail.return_value = True
            raw = {
                "tool_name": "Bash",
                "tool_input": {"command": "npm test"},
                "tool_result": {"exit_code": 0},
                "duration_ms": Thresholds.min_notify_duration * 1000 + 1000,
            }
            notify_complete(raw)
            mock_send.assert_called_once()


if __name__ == "__main__":
    main()

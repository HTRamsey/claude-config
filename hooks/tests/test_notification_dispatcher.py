"""Tests for notification dispatcher module."""
import json
from unittest.mock import patch, Mock

import pytest

from hooks.dispatchers.notification import (
    NotificationDispatcher,
    handle_notification,
)


class TestHandleNotification:
    """Tests for notification handling."""

    def test_permission_prompt(self):
        """Should handle permission prompt notifications."""
        ctx = {
            "event_type": "Notification",
            "notification_type": "permission_prompt",
            "tool_name": "Bash",
            "message": "Allow command execution?",
        }
        messages = handle_notification(ctx)
        assert isinstance(messages, list)

    def test_idle_prompt(self):
        """Should handle idle prompt notifications."""
        ctx = {
            "event_type": "Notification",
            "notification_type": "idle_prompt",
            "idle_seconds": 60,
        }
        messages = handle_notification(ctx)
        assert isinstance(messages, list)

    def test_auth_success(self):
        """Should handle auth success notifications."""
        ctx = {
            "event_type": "Notification",
            "notification_type": "auth_success",
        }
        messages = handle_notification(ctx)
        assert isinstance(messages, list)

    def test_elicitation_dialog(self):
        """Should handle elicitation dialog notifications."""
        ctx = {
            "event_type": "Notification",
            "notification_type": "elicitation_dialog",
            "mcp_server": "memory",
        }
        messages = handle_notification(ctx)
        assert isinstance(messages, list)

    def test_unknown_notification(self):
        """Should handle unknown notification types gracefully."""
        ctx = {
            "event_type": "Notification",
            "notification_type": "unknown_type",
        }
        messages = handle_notification(ctx)
        assert isinstance(messages, list)


class TestNotificationDispatcher:
    """Tests for NotificationDispatcher class."""

    def test_event_type(self):
        """Should have correct event type."""
        dispatcher = NotificationDispatcher()
        assert dispatcher.EVENT_TYPE == "Notification"

    def test_dispatcher_name(self):
        """Should have correct dispatcher name."""
        dispatcher = NotificationDispatcher()
        assert dispatcher.DISPATCHER_NAME == "notification_handler"

    @patch("hooks.dispatchers.notification.handle_notification")
    def test_handle_delegates(self, mock_handle):
        """Should delegate to handle_notification."""
        mock_handle.return_value = ["Test message"]
        dispatcher = NotificationDispatcher()
        ctx = {"event_type": "Notification", "notification_type": "test"}

        result = dispatcher.handle(ctx)

        mock_handle.assert_called_once_with(ctx)
        assert result == ["Test message"]

    def test_validate_event_correct(self):
        """Should validate Notification events."""
        dispatcher = NotificationDispatcher()
        assert dispatcher.validate_event({"event_type": "Notification"}) is True
        assert dispatcher.validate_event({"event": "Notification"}) is True

    def test_validate_event_wrong(self):
        """Should reject non-Notification events."""
        dispatcher = NotificationDispatcher()
        assert dispatcher.validate_event({"event_type": "Stop"}) is False
        assert dispatcher.validate_event({"event_type": "SessionStart"}) is False

"""Tests for subagent_stop dispatcher module."""
import json
from unittest.mock import patch, Mock

import pytest

from hooks.dispatchers.subagent_stop import (
    SubagentStopDispatcher,
    handle_subagent_stop,
)


class TestHandleSubagentStop:
    """Tests for subagent stop handling."""

    @patch("hooks.dispatchers.subagent_stop.subagent_lifecycle.handle_complete")
    def test_basic_stop(self, mock_handle_complete):
        """Should handle basic subagent stop."""
        ctx = {
            "event_type": "SubagentStop",
            "subagent_id": "abc123",
            "subagent_type": "Explore",
            "stop_reason": "completed",
        }
        messages = handle_subagent_stop(ctx)
        # Basic handler returns empty list (logging only)
        assert isinstance(messages, list)
        assert mock_handle_complete.called

    @patch("hooks.dispatchers.subagent_stop.subagent_lifecycle.handle_complete")
    def test_stop_with_error(self, mock_handle_complete):
        """Should handle subagent stop with error."""
        ctx = {
            "event_type": "SubagentStop",
            "subagent_id": "abc123",
            "subagent_type": "test-generator",
            "stop_reason": "error",
            "error": "Timeout exceeded",
        }
        messages = handle_subagent_stop(ctx)
        assert isinstance(messages, list)

    @patch("hooks.dispatchers.subagent_stop.subagent_lifecycle.handle_complete")
    def test_stop_with_output(self, mock_handle_complete):
        """Should handle subagent stop with output."""
        ctx = {
            "event_type": "SubagentStop",
            "subagent_id": "xyz789",
            "subagent_type": "code-reviewer",
            "stop_reason": "completed",
            "output": "Review complete: 3 issues found",
        }
        messages = handle_subagent_stop(ctx)
        assert isinstance(messages, list)


class TestSubagentStopDispatcher:
    """Tests for SubagentStopDispatcher class."""

    def test_event_type(self):
        """Should have correct event type."""
        dispatcher = SubagentStopDispatcher()
        assert dispatcher.EVENT_TYPE == "SubagentStop"

    def test_dispatcher_name(self):
        """Should have correct dispatcher name."""
        dispatcher = SubagentStopDispatcher()
        assert dispatcher.DISPATCHER_NAME == "subagent_stop_handler"

    @patch("hooks.dispatchers.subagent_stop.handle_subagent_stop")
    def test_handle_delegates(self, mock_handle):
        """Should delegate to handle_subagent_stop."""
        mock_handle.return_value = ["Test message"]
        dispatcher = SubagentStopDispatcher()
        ctx = {"event_type": "SubagentStop", "subagent_type": "test"}

        result = dispatcher.handle(ctx)

        mock_handle.assert_called_once_with(ctx)
        assert result == ["Test message"]

    def test_validate_event_correct(self):
        """Should validate SubagentStop events."""
        dispatcher = SubagentStopDispatcher()
        assert dispatcher.validate_event({"event_type": "SubagentStop"}) is True
        assert dispatcher.validate_event({"event": "SubagentStop"}) is True

    def test_validate_event_wrong(self):
        """Should reject non-SubagentStop events."""
        dispatcher = SubagentStopDispatcher()
        assert dispatcher.validate_event({"event_type": "Stop"}) is False
        assert dispatcher.validate_event({"event_type": "SessionEnd"}) is False

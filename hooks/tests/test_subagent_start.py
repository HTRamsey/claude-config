"""Tests for subagent_start dispatcher module."""
from unittest.mock import patch, Mock

import pytest

from hooks.dispatchers.subagent_start import (
    SubagentStartDispatcher,
    handle_subagent_start,
)


class TestHandleSubagentStart:
    """Tests for subagent start handling."""

    @patch("hooks.dispatchers.subagent_start.subagent_lifecycle.handle_start")
    def test_basic_start(self, mock_handle_start):
        """Should handle basic subagent start."""
        ctx = {
            "event_type": "SubagentStart",
            "subagent_id": "abc123",
            "subagent_type": "Explore",
            "description": "Search for auth patterns",
        }
        messages = handle_subagent_start(ctx)
        assert isinstance(messages, list)
        assert mock_handle_start.called

    @patch("hooks.dispatchers.subagent_start.subagent_lifecycle.handle_start")
    def test_start_with_prompt(self, mock_handle_start):
        """Should handle subagent start with prompt."""
        ctx = {
            "event_type": "SubagentStart",
            "subagent_id": "xyz789",
            "subagent_type": "code-reviewer",
            "prompt": "Review the authentication module for security issues",
        }
        messages = handle_subagent_start(ctx)
        assert isinstance(messages, list)

    @patch("hooks.dispatchers.subagent_start.subagent_lifecycle.handle_start")
    def test_start_background_agent(self, mock_handle_start):
        """Should handle background agent start."""
        ctx = {
            "event_type": "SubagentStart",
            "subagent_id": "bg001",
            "subagent_type": "test-generator",
            "run_in_background": True,
        }
        messages = handle_subagent_start(ctx)
        assert isinstance(messages, list)


class TestSubagentStartDispatcher:
    """Tests for SubagentStartDispatcher class."""

    def test_event_type(self):
        """Should have correct event type."""
        dispatcher = SubagentStartDispatcher()
        assert dispatcher.EVENT_TYPE == "SubagentStart"

    def test_dispatcher_name(self):
        """Should have correct dispatcher name."""
        dispatcher = SubagentStartDispatcher()
        assert dispatcher.DISPATCHER_NAME == "subagent_start_handler"

    @patch("hooks.dispatchers.subagent_start.handle_subagent_start")
    def test_handle_delegates(self, mock_handle):
        """Should delegate to handle_subagent_start."""
        mock_handle.return_value = ["Test message"]
        dispatcher = SubagentStartDispatcher()
        ctx = {"event_type": "SubagentStart", "subagent_type": "test"}

        result = dispatcher.handle(ctx)

        mock_handle.assert_called_once_with(ctx)
        assert result == ["Test message"]

    def test_validate_event_correct(self):
        """Should validate SubagentStart events."""
        dispatcher = SubagentStartDispatcher()
        assert dispatcher.validate_event({"event_type": "SubagentStart"}) is True
        assert dispatcher.validate_event({"event": "SubagentStart"}) is True

    def test_validate_event_wrong(self):
        """Should reject non-SubagentStart events."""
        dispatcher = SubagentStartDispatcher()
        assert dispatcher.validate_event({"event_type": "SubagentStop"}) is False
        assert dispatcher.validate_event({"event_type": "PreToolUse"}) is False

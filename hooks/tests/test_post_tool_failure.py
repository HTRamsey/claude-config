"""Tests for post_tool_failure dispatcher module."""
from unittest.mock import patch, Mock

import pytest

from hooks.dispatchers.post_tool_failure import (
    PostToolFailureDispatcher,
    handle_tool_failure,
)


class TestHandleToolFailure:
    """Tests for tool failure handling."""

    @patch("hooks.dispatchers.post_tool_failure.log_event")
    def test_bash_failure(self, mock_log):
        """Should handle Bash command failure."""
        ctx = {
            "event_type": "PostToolUseFailure",
            "tool_name": "Bash",
            "tool_input": {"command": "npm test"},
            "error": "Exit code 1",
            "exit_code": 1,
        }
        messages = handle_tool_failure(ctx)
        assert isinstance(messages, list)

    @patch("hooks.dispatchers.post_tool_failure.log_event")
    def test_read_failure(self, mock_log):
        """Should handle Read tool failure."""
        ctx = {
            "event_type": "PostToolUseFailure",
            "tool_name": "Read",
            "tool_input": {"file_path": "/nonexistent/file.txt"},
            "error": "File not found",
        }
        messages = handle_tool_failure(ctx)
        assert isinstance(messages, list)

    @patch("hooks.dispatchers.post_tool_failure.log_event")
    def test_edit_failure(self, mock_log):
        """Should handle Edit tool failure."""
        ctx = {
            "event_type": "PostToolUseFailure",
            "tool_name": "Edit",
            "tool_input": {"file_path": "/test/file.py", "old_string": "foo"},
            "error": "String not found in file",
        }
        messages = handle_tool_failure(ctx)
        assert isinstance(messages, list)

    @patch("hooks.dispatchers.post_tool_failure.log_event")
    def test_task_failure(self, mock_log):
        """Should handle Task tool failure."""
        ctx = {
            "event_type": "PostToolUseFailure",
            "tool_name": "Task",
            "tool_input": {"subagent_type": "test-generator", "prompt": "Generate tests"},
            "error": "Timeout exceeded",
        }
        messages = handle_tool_failure(ctx)
        assert isinstance(messages, list)

    @patch("hooks.dispatchers.post_tool_failure.log_event")
    def test_unknown_tool_failure(self, mock_log):
        """Should handle unknown tool failure gracefully."""
        ctx = {
            "event_type": "PostToolUseFailure",
            "tool_name": "UnknownTool",
            "error": "Some error",
        }
        messages = handle_tool_failure(ctx)
        assert isinstance(messages, list)


class TestPostToolFailureDispatcher:
    """Tests for PostToolFailureDispatcher class."""

    def test_event_type(self):
        """Should have correct event type."""
        dispatcher = PostToolFailureDispatcher()
        assert dispatcher.EVENT_TYPE == "PostToolUseFailure"

    def test_dispatcher_name(self):
        """Should have correct dispatcher name."""
        dispatcher = PostToolFailureDispatcher()
        assert dispatcher.DISPATCHER_NAME == "post_tool_failure_handler"

    @patch("hooks.dispatchers.post_tool_failure.handle_tool_failure")
    def test_handle_delegates(self, mock_handle):
        """Should delegate to handle_tool_failure."""
        mock_handle.return_value = ["Test message"]
        dispatcher = PostToolFailureDispatcher()
        ctx = {"event_type": "PostToolUseFailure", "tool_name": "Bash"}

        result = dispatcher.handle(ctx)

        mock_handle.assert_called_once_with(ctx)
        assert result == ["Test message"]

    def test_validate_event_correct(self):
        """Should validate PostToolUseFailure events."""
        dispatcher = PostToolFailureDispatcher()
        assert dispatcher.validate_event({"event_type": "PostToolUseFailure"}) is True
        assert dispatcher.validate_event({"event": "PostToolUseFailure"}) is True

    def test_validate_event_wrong(self):
        """Should reject non-PostToolUseFailure events."""
        dispatcher = PostToolFailureDispatcher()
        assert dispatcher.validate_event({"event_type": "PostToolUse"}) is False
        assert dispatcher.validate_event({"event_type": "PreToolUse"}) is False

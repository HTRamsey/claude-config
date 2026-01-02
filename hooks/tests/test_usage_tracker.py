"""Tests for usage tracking functionality (now in subagent_lifecycle)."""
from unittest.mock import patch

import pytest

from hooks.handlers.subagent_lifecycle import handle_start, handle_skill


class TestAgentTracking:
    """Tests for Task/agent usage tracking in handle_start."""

    @patch('hooks.handlers.subagent_lifecycle.record_usage')
    @patch('hooks.handlers.subagent_lifecycle.update_session_state')
    @patch('hooks.handlers.subagent_lifecycle.get_session_state')
    @patch('hooks.handlers.subagent_lifecycle.log_event')
    def test_tracks_agent_type(self, mock_log, mock_get, mock_update, mock_record):
        """Should track Task tool with agent type."""
        mock_get.return_value = {}
        ctx = {
            "tool_name": "Task",
            "tool_input": {"subagent_type": "Explore", "prompt": "Find files"}
        }
        handle_start(ctx)

        mock_record.assert_called_once_with("agents", "Explore")

    @patch('hooks.handlers.subagent_lifecycle.record_usage')
    @patch('hooks.handlers.subagent_lifecycle.update_session_state')
    @patch('hooks.handlers.subagent_lifecycle.get_session_state')
    @patch('hooks.handlers.subagent_lifecycle.log_event')
    def test_handles_missing_subagent_type(self, mock_log, mock_get, mock_update, mock_record):
        """Should handle missing subagent_type gracefully."""
        mock_get.return_value = {}
        ctx = {
            "tool_name": "Task",
            "tool_input": {"prompt": "Do something"}
        }
        handle_start(ctx)

        # Still called with "unknown" as fallback
        mock_record.assert_called_once_with("agents", "unknown")


class TestSkillTracking:
    """Tests for Skill tool usage tracking."""

    @patch('hooks.handlers.subagent_lifecycle.record_usage')
    def test_tracks_skill_name(self, mock_record):
        """Should track Skill tool usage."""
        ctx = {
            "tool_name": "Skill",
            "tool_input": {"skill": "systematic-debugging"}
        }
        handle_skill(ctx)

        mock_record.assert_called_once_with("skills", "systematic-debugging")

    @patch('hooks.handlers.subagent_lifecycle.record_usage')
    def test_ignores_skill_without_name(self, mock_record):
        """Should not track Skill without skill name."""
        ctx = {
            "tool_name": "Skill",
            "tool_input": {}
        }
        handle_skill(ctx)

        mock_record.assert_not_called()

    @patch('hooks.handlers.subagent_lifecycle.record_usage')
    def test_ignores_empty_skill_name(self, mock_record):
        """Should not track empty skill name."""
        ctx = {
            "tool_name": "Skill",
            "tool_input": {"skill": ""}
        }
        handle_skill(ctx)

        mock_record.assert_not_called()


class TestEmptyContext:
    """Tests for edge cases with empty/missing context."""

    @patch('hooks.handlers.subagent_lifecycle.record_usage')
    def test_empty_skill_context(self, mock_record):
        """Should handle empty context for skill tracking."""
        handle_skill({})

        mock_record.assert_not_called()

    @patch('hooks.handlers.subagent_lifecycle.record_usage')
    @patch('hooks.handlers.subagent_lifecycle.update_session_state')
    @patch('hooks.handlers.subagent_lifecycle.get_session_state')
    @patch('hooks.handlers.subagent_lifecycle.log_event')
    def test_missing_tool_input(self, mock_log, mock_get, mock_update, mock_record):
        """Should handle missing tool_input in handle_start."""
        mock_get.return_value = {}
        ctx = {"tool_name": "Task"}
        handle_start(ctx)

        # Still tracks with "unknown" fallback
        mock_record.assert_called_once_with("agents", "unknown")

"""Tests for usage_tracker handler."""
from unittest.mock import patch

import pytest

from hooks.handlers.usage_tracker import handle, BUILTIN_COMMANDS


class TestAgentTracking:
    """Tests for Task/agent usage tracking."""

    @patch('hooks.handlers.usage_tracker.record_usage')
    def test_tracks_agent_type(self, mock_record):
        """Should track Task tool with agent type."""
        ctx = {
            "tool_name": "Task",
            "tool_input": {"subagent_type": "Explore", "prompt": "Find files"}
        }
        result = handle(ctx)

        assert result is None
        mock_record.assert_called_once_with("agents", "Explore")

    @patch('hooks.handlers.usage_tracker.record_usage')
    def test_ignores_task_without_subagent_type(self, mock_record):
        """Should not track Task without subagent_type."""
        ctx = {
            "tool_name": "Task",
            "tool_input": {"prompt": "Do something"}
        }
        result = handle(ctx)

        assert result is None
        mock_record.assert_not_called()

    @patch('hooks.handlers.usage_tracker.record_usage')
    def test_ignores_empty_subagent_type(self, mock_record):
        """Should not track empty subagent_type."""
        ctx = {
            "tool_name": "Task",
            "tool_input": {"subagent_type": "", "prompt": "Do something"}
        }
        result = handle(ctx)

        assert result is None
        mock_record.assert_not_called()


class TestSkillTracking:
    """Tests for Skill tool usage tracking."""

    @patch('hooks.handlers.usage_tracker.record_usage')
    def test_tracks_skill_name(self, mock_record):
        """Should track Skill tool usage."""
        ctx = {
            "tool_name": "Skill",
            "tool_input": {"skill": "systematic-debugging"}
        }
        result = handle(ctx)

        assert result is None
        mock_record.assert_called_once_with("skills", "systematic-debugging")

    @patch('hooks.handlers.usage_tracker.record_usage')
    def test_ignores_skill_without_name(self, mock_record):
        """Should not track Skill without skill name."""
        ctx = {
            "tool_name": "Skill",
            "tool_input": {}
        }
        result = handle(ctx)

        assert result is None
        mock_record.assert_not_called()

    @patch('hooks.handlers.usage_tracker.record_usage')
    def test_ignores_empty_skill_name(self, mock_record):
        """Should not track empty skill name."""
        ctx = {
            "tool_name": "Skill",
            "tool_input": {"skill": ""}
        }
        result = handle(ctx)

        assert result is None
        mock_record.assert_not_called()


class TestCommandTracking:
    """Tests for slash command usage tracking."""

    @patch('hooks.handlers.usage_tracker.record_usage')
    def test_tracks_custom_command(self, mock_record):
        """Should track custom slash commands."""
        ctx = {"user_prompt": "/commit"}
        result = handle(ctx)

        assert result is None
        mock_record.assert_called_once_with("commands", "commit")

    @patch('hooks.handlers.usage_tracker.record_usage')
    def test_tracks_command_with_args(self, mock_record):
        """Should track command name only, not args."""
        ctx = {"user_prompt": "/review src/main.py"}
        result = handle(ctx)

        assert result is None
        mock_record.assert_called_once_with("commands", "review")

    @patch('hooks.handlers.usage_tracker.record_usage')
    def test_ignores_builtin_commands(self, mock_record):
        """Should not track builtin commands."""
        for cmd in ["help", "clear", "compact", "cost", "doctor"]:
            mock_record.reset_mock()
            ctx = {"user_prompt": f"/{cmd}"}
            result = handle(ctx)

            assert result is None
            mock_record.assert_not_called()

    @patch('hooks.handlers.usage_tracker.record_usage')
    def test_ignores_non_slash_prompts(self, mock_record):
        """Should not track regular prompts."""
        ctx = {"user_prompt": "Help me with something"}
        result = handle(ctx)

        assert result is None
        mock_record.assert_not_called()

    @patch('hooks.handlers.usage_tracker.record_usage')
    def test_handles_prompt_field(self, mock_record):
        """Should also check 'prompt' field."""
        ctx = {"prompt": "/test"}
        result = handle(ctx)

        assert result is None
        mock_record.assert_called_once_with("commands", "test")

    @patch('hooks.handlers.usage_tracker.record_usage')
    def test_command_case_insensitive(self, mock_record):
        """Should normalize command to lowercase."""
        ctx = {"user_prompt": "/COMMIT"}
        result = handle(ctx)

        assert result is None
        mock_record.assert_called_once_with("commands", "commit")

    @patch('hooks.handlers.usage_tracker.record_usage')
    def test_handles_whitespace(self, mock_record):
        """Should handle leading/trailing whitespace."""
        ctx = {"user_prompt": "  /debug  "}
        result = handle(ctx)

        assert result is None
        mock_record.assert_called_once_with("commands", "debug")


class TestOtherTools:
    """Tests for non-tracked tool usage."""

    @patch('hooks.handlers.usage_tracker.record_usage')
    def test_ignores_other_tools(self, mock_record):
        """Should not track other tools like Read, Write, etc."""
        for tool in ["Read", "Write", "Edit", "Bash", "Grep", "Glob"]:
            mock_record.reset_mock()
            ctx = {"tool_name": tool, "tool_input": {"file_path": "/some/file"}}
            result = handle(ctx)

            assert result is None
            mock_record.assert_not_called()


class TestBuiltinCommands:
    """Tests for builtin command list."""

    def test_builtin_list_complete(self):
        """Verify builtin commands list contains expected items."""
        expected = {"help", "clear", "compact", "cost", "doctor", "status"}
        assert expected.issubset(BUILTIN_COMMANDS)

    def test_builtin_list_is_set(self):
        """Builtin commands should be a set for O(1) lookup."""
        assert isinstance(BUILTIN_COMMANDS, set)


class TestEmptyContext:
    """Tests for edge cases with empty/missing context."""

    @patch('hooks.handlers.usage_tracker.record_usage')
    def test_empty_context(self, mock_record):
        """Should handle empty context gracefully."""
        result = handle({})

        assert result is None
        mock_record.assert_not_called()

    @patch('hooks.handlers.usage_tracker.record_usage')
    def test_missing_tool_input(self, mock_record):
        """Should handle missing tool_input."""
        ctx = {"tool_name": "Task"}
        result = handle(ctx)

        assert result is None
        mock_record.assert_not_called()

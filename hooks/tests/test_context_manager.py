#!/usr/bin/env python3
"""Unit tests for context_manager.py functions.

Tests for context preservation, checkpoint handling, and token monitoring.
"""

import sys
import time
import tempfile
import json
from pathlib import Path
from datetime import datetime
from unittest import TestCase, main
from unittest.mock import patch, MagicMock, mock_open

from hooks.handlers.context_manager import (
    get_claude_md_content,
    get_active_todos,
    get_key_context,
    handle_pre_tool_use,
    handle_post_tool_use,
    handle_pre_compact,
    check_context,
    TOKEN_WARNING_THRESHOLD,
    TOKEN_CRITICAL_THRESHOLD,
)
from hooks.hook_sdk import PreToolUseContext, PostToolUseContext


class TestGetClaudeMdContent(TestCase):
    """Tests for get_claude_md_content function."""

    def test_reads_claude_md_from_project_root(self):
        """Reads CLAUDE.md from project root if it exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            claude_md = Path(tmpdir) / "CLAUDE.md"
            claude_md.write_text("# Test Project\n\nProject instructions here.")

            result = get_claude_md_content(tmpdir)

            self.assertIn("Test Project", result)
            self.assertIn("preserved", result)

    def test_reads_claude_md_from_dot_claude(self):
        """Falls back to .claude/CLAUDE.md if root doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dot_claude = Path(tmpdir) / ".claude"
            dot_claude.mkdir()
            claude_md = dot_claude / "CLAUDE.md"
            claude_md.write_text("# Config instructions")

            result = get_claude_md_content(tmpdir)

            self.assertIn("Config instructions", result)

    def test_truncates_long_content(self):
        """Truncates content to first 2000 chars."""
        with tempfile.TemporaryDirectory() as tmpdir:
            claude_md = Path(tmpdir) / "CLAUDE.md"
            long_content = "x" * 3000
            claude_md.write_text(long_content)

            result = get_claude_md_content(tmpdir)

            # Should contain truncated content (2000 chars + header)
            self.assertLess(len(result), 2050)

    def test_returns_empty_if_no_claude_md(self):
        """Returns empty string if no CLAUDE.md exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = get_claude_md_content(tmpdir)
            self.assertEqual(result, "")

    def test_handles_read_error_gracefully(self):
        """Returns empty string if read fails."""
        result = get_claude_md_content("/nonexistent/directory")
        self.assertEqual(result, "")


class TestGetActiveTodos(TestCase):
    """Tests for get_active_todos function."""

    def test_extracts_pending_todos(self):
        """Extracts pending todos from context."""
        raw = {
            "todos": [
                {"content": "Fix bug", "status": "pending"},
                {"content": "Write tests", "status": "pending"},
                {"content": "Done task", "status": "done"},
            ]
        }

        result = get_active_todos(raw)

        self.assertIn("Fix bug", result)
        self.assertIn("Write tests", result)
        self.assertNotIn("Done task", result)
        self.assertIn("preserved", result)

    def test_extracts_in_progress_todos(self):
        """Extracts in-progress todos with different marker."""
        raw = {
            "todos": [
                {"content": "Active task", "status": "in_progress"},
                {"content": "Pending task", "status": "pending"},
            ]
        }

        result = get_active_todos(raw)

        self.assertIn("Active task", result)
        self.assertIn("Pending task", result)
        # in_progress uses → marker, pending uses ○
        self.assertIn("→", result)
        self.assertIn("○", result)

    def test_limits_to_10_todos(self):
        """Limits output to 10 todos."""
        todos = [{"content": f"Task {i}", "status": "pending"} for i in range(20)]
        raw = {"todos": todos}

        result = get_active_todos(raw)

        # Count lines (header + 10 todos)
        lines = result.split("\n")
        self.assertEqual(len(lines), 11)  # Header + 10 todos

    def test_returns_empty_for_inactive_todo_states(self):
        """Returns empty for no todos, completed todos, or missing todos key."""
        test_cases = [
            ({"todos": []}, ""),
            ({"todos": [{"content": "Done", "status": "done"}, {"content": "Cancelled", "status": "cancelled"}]}, ""),
            ({}, ""),
        ]
        for raw, expected in test_cases:
            with self.subTest(raw=raw):
                result = get_active_todos(raw)
                self.assertEqual(result, expected)


class TestGetKeyContext(TestCase):
    """Tests for get_key_context function."""

    def test_combines_all_context_elements(self):
        """Combines CLAUDE.md, todos, cwd, and session."""
        with tempfile.TemporaryDirectory() as tmpdir:
            claude_md = Path(tmpdir) / "CLAUDE.md"
            claude_md.write_text("# Project")

            raw = {
                "cwd": tmpdir,
                "session_id": "test-session-12345",
                "todos": [{"content": "Task", "status": "pending"}]
            }

            result = get_key_context(raw)

            self.assertIn("Project", result)
            self.assertIn("Task", result)
            self.assertIn(tmpdir, result)
            # Session ID is truncated to first 8 chars: "test-ses..."
            self.assertIn("test-ses", result)

    def test_handles_missing_elements_gracefully(self):
        """Works with missing context elements."""
        raw = {}
        result = get_key_context(raw)
        # Should return something, even if minimal
        self.assertIsInstance(result, str)



class TestHandlePreToolUse(TestCase):
    """Tests for handle_pre_tool_use function."""

    @patch("hooks.handlers.context_manager.load_state")
    @patch("hooks.handlers.context_manager.is_risky_operation")
    @patch("hooks.handlers.context_manager.should_checkpoint")
    @patch("hooks.handlers.context_manager.save_checkpoint_entry")
    @patch("hooks.handlers.context_manager.get_session_id")
    @patch("hooks.handlers.context_manager.log_event")
    def test_checkpoints_risky_edit(self, mock_log, mock_session, mock_save, mock_should, mock_risky, mock_load):
        """Creates checkpoint for risky Edit operations."""
        mock_session.return_value = "test-session"
        mock_load.return_value = {"last_checkpoint": 0}
        mock_risky.return_value = (True, "large edit")
        mock_should.return_value = True

        raw = {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": "/test/file.py",
                "old_string": "old",
                "new_string": "x" * 1000
            },
            "cwd": "/test"
        }

        result = handle_pre_tool_use(raw)

        self.assertIsNotNone(result)
        # Response.allow returns dict with hookSpecificOutput.permissionDecisionReason
        reason = result.get("hookSpecificOutput", {}).get("permissionDecisionReason", "")
        self.assertIn("Checkpoint", reason)
        mock_save.assert_called_once()

    @patch("hooks.handlers.context_manager.load_state")
    @patch("hooks.handlers.context_manager.is_risky_operation")
    @patch("hooks.handlers.context_manager.should_checkpoint")
    def test_checkpoints_risky_write(self, mock_should, mock_risky, mock_load):
        """Creates checkpoint for risky Write operations."""
        mock_load.return_value = {"last_checkpoint": 0}
        mock_risky.return_value = (True, "contains 'DROP TABLE' operation")
        mock_should.return_value = True

        raw = {
            "tool_name": "Write",
            "tool_input": {
                "file_path": "/test/schema.sql",
                "content": "DROP TABLE users;"
            }
        }

        result = handle_pre_tool_use(raw)

        self.assertIsNotNone(result)

    @patch("hooks.handlers.context_manager.load_state")
    @patch("hooks.handlers.context_manager.is_risky_operation")
    def test_skips_non_risky_operations(self, mock_risky, mock_load):
        """Skips checkpoint for non-risky operations."""
        mock_load.return_value = {"last_checkpoint": 0}
        mock_risky.return_value = (False, "")

        raw = {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": "/test/file.py",
                "old_string": "old",
                "new_string": "new"
            }
        }

        result = handle_pre_tool_use(raw)

        self.assertIsNone(result)

    @patch("hooks.handlers.context_manager.load_state")
    @patch("hooks.handlers.context_manager.is_risky_operation")
    @patch("hooks.handlers.context_manager.should_checkpoint")
    def test_skips_if_checkpoint_too_recent(self, mock_should, mock_risky, mock_load):
        """Skips checkpoint if one was created recently."""
        mock_load.return_value = {"last_checkpoint": time.time()}
        mock_risky.return_value = (True, "large edit")
        mock_should.return_value = False

        raw = {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": "/test/file.py",
                "content": "x" * 1000
            }
        }

        result = handle_pre_tool_use(raw)

        self.assertIsNone(result)


    def test_handles_missing_file_path(self):
        """Returns None if file_path is missing."""
        raw = {
            "tool_name": "Edit",
            "tool_input": {}
        }

        result = handle_pre_tool_use(raw)

        self.assertIsNone(result)


class TestHandlePostToolUse(TestCase):
    """Tests for handle_post_tool_use function."""

    @patch("hooks.handlers.context_manager.save_error_backup")
    def test_saves_backup_on_command_failure(self, mock_save):
        """Saves backup when Bash command fails."""
        mock_save.return_value = "/path/to/backup.json"

        raw = {
            "tool_name": "Bash",
            "tool_input": {"command": "make test"},
            "tool_result": {
                "exit_code": 1,
                "output": "Error: compilation failed"
            }
        }

        result = handle_post_tool_use(raw)

        mock_save.assert_called_once()
        # Returns None (silent backup)
        self.assertIsNone(result)

    @patch("hooks.handlers.context_manager.save_error_backup")
    def test_skips_backup_on_success(self, mock_save):
        """Skips backup when command succeeds."""
        raw = {
            "tool_name": "Bash",
            "tool_input": {"command": "make test"},
            "tool_result": {"exit_code": 0, "output": "All tests passed"}
        }

        result = handle_post_tool_use(raw)

        mock_save.assert_not_called()
        self.assertIsNone(result)


    def test_handles_missing_exit_code(self):
        """Returns None if exit_code is missing."""
        raw = {
            "tool_name": "Bash",
            "tool_input": {"command": "echo test"},
            "tool_result": {"output": "test"}
        }

        result = handle_post_tool_use(raw)

        self.assertIsNone(result)


class TestHandlePreCompact(TestCase):
    """Tests for handle_pre_compact function."""

    @patch("hooks.handlers.context_manager.backup_transcript")
    @patch("hooks.handlers.context_manager.update_session_state")
    @patch("hooks.handlers.context_manager.get_key_context")
    def test_backs_up_transcript(self, mock_context, mock_update, mock_backup):
        """Backs up transcript before compaction."""
        mock_backup.return_value = "/backups/transcript-20260101.jsonl"
        mock_context.return_value = "Key context"

        raw = {"transcript_path": "/path/to/transcript.jsonl"}

        result = handle_pre_compact(raw)

        mock_backup.assert_called_once_with("/path/to/transcript.jsonl", reason="pre_compact")
        mock_update.assert_called_once()

    @patch("hooks.handlers.context_manager.backup_transcript")
    @patch("hooks.handlers.context_manager.update_session_state")
    @patch("hooks.handlers.context_manager.get_key_context")
    def test_preserves_key_context(self, mock_context, mock_update, mock_backup):
        """Includes key context in preservation message."""
        mock_backup.return_value = "/backups/transcript.jsonl"
        mock_context.return_value = "[Project CLAUDE.md preserved]\n# Test"

        raw = {"transcript_path": "/path/to/transcript.jsonl"}

        result = handle_pre_compact(raw)

        self.assertIsNotNone(result)
        self.assertIn("CLAUDE.md", result["message"])

    @patch("hooks.handlers.context_manager.backup_transcript")
    @patch("hooks.handlers.context_manager.update_session_state")
    @patch("hooks.handlers.context_manager.get_key_context")
    def test_includes_learning_reminder(self, mock_context, mock_update, mock_backup):
        """Includes learning reminder if learnings directory exists."""
        mock_backup.return_value = "/backups/transcript.jsonl"
        mock_context.return_value = ""

        with tempfile.TemporaryDirectory() as tmpdir:
            learnings_dir = Path(tmpdir) / "learnings"
            learnings_dir.mkdir()
            (learnings_dir / "debugging.md").write_text("# Debugging")

            with patch("hooks.handlers.context_manager.Path.home", return_value=Path(tmpdir).parent):
                # Need to mock .claude location
                with patch.object(Path, "exists", return_value=True):
                    with patch.object(Path, "glob", return_value=[learnings_dir / "debugging.md"]):
                        raw = {"transcript_path": "/path/to/transcript.jsonl"}

                        result = handle_pre_compact(raw)

                        self.assertIsNotNone(result)
                        self.assertIn("Learning Reminder", result["message"])

    def test_returns_none_if_no_transcript_path(self):
        """Returns None if transcript_path is missing."""
        raw = {}
        result = handle_pre_compact(raw)
        self.assertIsNone(result)


class TestCheckContext(TestCase):
    """Tests for check_context function."""

    @patch("hooks.handlers.context_manager.get_transcript_size")
    def test_warns_at_warning_threshold(self, mock_size):
        """Warns when token count reaches warning threshold."""
        mock_size.return_value = (TOKEN_WARNING_THRESHOLD + 100, 50)

        raw = {"transcript_path": "/path/to/transcript.jsonl"}

        result = check_context(raw)

        self.assertIsNotNone(result)
        self.assertIn("Context Monitor", result["message"])
        self.assertIn("/compact", result["message"])

    @patch("hooks.handlers.context_manager.get_transcript_size")
    @patch("hooks.handlers.context_manager.backup_transcript")
    @patch("hooks.handlers.context_manager.get_session_summary")
    def test_critical_threshold_backs_up_and_warns(self, mock_summary, mock_backup, mock_size):
        """Critical threshold triggers backup and detailed warning."""
        mock_size.return_value = (TOKEN_CRITICAL_THRESHOLD + 100, 100)
        mock_backup.return_value = "/backups/transcript.jsonl"
        mock_summary.return_value = "Edited: test.py | Tools: Read:10"

        raw = {"transcript_path": "/path/to/transcript.jsonl"}

        result = check_context(raw)

        self.assertIsNotNone(result)
        mock_backup.assert_called_once()
        self.assertIn("CRITICAL", result["message"])
        self.assertIn("backed up", result["message"])
        self.assertIn("Edited: test.py", result["message"])

    @patch("hooks.handlers.context_manager.get_transcript_size")
    def test_no_warning_below_threshold(self, mock_size):
        """No warning when below threshold."""
        mock_size.return_value = (TOKEN_WARNING_THRESHOLD - 1000, 20)

        raw = {"transcript_path": "/path/to/transcript.jsonl"}

        result = check_context(raw)

        self.assertIsNone(result)

    @patch("hooks.handlers.context_manager.get_transcript_size")
    def test_handles_missing_transcript_path(self, mock_size):
        """Returns None if transcript_path is missing."""
        mock_size.return_value = (0, 0)

        raw = {}

        result = check_context(raw)

        # Should handle gracefully
        self.assertIsNone(result)


if __name__ == "__main__":
    main()

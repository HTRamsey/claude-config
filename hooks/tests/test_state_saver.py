#!/usr/bin/env python3
"""Unit tests for state_saver.py functions."""

import sys
import time
import tempfile
import json
from pathlib import Path
from unittest import TestCase, main
from unittest.mock import patch, MagicMock
from datetime import datetime

# Add parent directory to path for imports
from hooks.handlers.context_manager import (
    is_risky_operation,
    should_checkpoint,
    save_checkpoint_entry,
    save_error_backup,
    rotate_error_backups,
    load_state,
    save_state,
    ERROR_BACKUP_DIR,
)
from hooks.handlers.context_manager import (
    handle_pre_tool_use,
    handle_post_tool_use,
    handle_pre_compact,
    get_claude_md_content,
    get_active_todos,
    get_key_context,
)
from hooks.hook_sdk import PreToolUseContext, PostToolUseContext


class TestIsRiskyOperation(TestCase):
    """Tests for is_risky_operation function."""

    def test_file_path_with_risky_pattern(self):
        """File paths matching risky patterns should be detected."""
        # The patterns check the file path, not content
        risky, reason = is_risky_operation("rm -rf backup", "content")
        self.assertTrue(risky)
        self.assertIn("risky pattern", reason)

    def test_git_hard_reset_is_risky(self):
        """Git hard reset should be detected as risky via keyword."""
        risky, reason = is_risky_operation("commands.txt", "git reset --hard HEAD")
        self.assertTrue(risky)
        # Detected via 'reset' keyword, not pattern
        self.assertIn("reset", reason)

    def test_small_edit_not_risky(self):
        """Small edits without keywords should not be risky."""
        risky, reason = is_risky_operation("foo.py", "a = 1")
        self.assertFalse(risky)
        self.assertEqual(reason, "")

    def test_delete_keyword_is_risky(self):
        """Content with 'delete' keyword should be risky."""
        risky, reason = is_risky_operation("script.py", "delete all files")
        self.assertTrue(risky)
        self.assertIn("delete", reason)

    def test_drop_keyword_is_risky(self):
        """Content with 'drop' keyword should be risky."""
        risky, reason = is_risky_operation("sql.py", "DROP TABLE users")
        self.assertTrue(risky)
        self.assertIn("drop", reason)

    def test_large_content_is_risky(self):
        """Content over 500 chars should be risky."""
        large_content = "x" * 501
        risky, reason = is_risky_operation("file.txt", large_content)
        self.assertTrue(risky)
        self.assertIn("large edit", reason)

    def test_boundary_size_not_risky(self):
        """Content at exactly 500 chars should not be risky."""
        content = "x" * 500
        risky, reason = is_risky_operation("file.txt", content)
        self.assertFalse(risky)

    def test_case_insensitive_keyword_match(self):
        """Keywords should match case-insensitively."""
        risky, reason = is_risky_operation("file.py", "DELETE FROM table")
        self.assertTrue(risky)
        self.assertIn("delete", reason.lower())

    def test_normal_python_file_not_risky(self):
        """Normal Python files with safe content should not be risky."""
        risky, reason = is_risky_operation("app.py", "def hello():\n    print('hi')")
        self.assertFalse(risky)


class TestShouldCheckpoint(TestCase):
    """Tests for should_checkpoint function."""

    def test_checkpoint_needed_when_old(self):
        """Should checkpoint when last checkpoint is old enough."""
        old_time = time.time() - 400  # 400 seconds ago (> 300s interval)
        state = {"last_checkpoint": old_time}
        self.assertTrue(should_checkpoint(state))

    def test_checkpoint_not_needed_when_recent(self):
        """Should not checkpoint when last checkpoint is recent."""
        recent_time = time.time() - 100  # 100 seconds ago (< 300s interval)
        state = {"last_checkpoint": recent_time}
        self.assertFalse(should_checkpoint(state))

    def test_checkpoint_needed_when_missing(self):
        """Should checkpoint when last_checkpoint is missing."""
        state = {}
        self.assertTrue(should_checkpoint(state))

    def test_checkpoint_boundary_case(self):
        """Test boundary at exactly 300 seconds."""
        # Set to 299.5 seconds ago to avoid timing issues
        boundary_time = time.time() - 299.5
        state = {"last_checkpoint": boundary_time}
        # Should be False since < 300 seconds
        self.assertFalse(should_checkpoint(state))


class TestSaveCheckpointEntry(TestCase):
    """Tests for save_checkpoint_entry function."""

    def setUp(self):
        """Clear checkpoint state before each test."""
        save_state({"last_checkpoint": 0, "checkpoints": []})

    @patch('hooks.handlers.context_manager.save_state')
    @patch('hooks.handlers.context_manager.load_state')
    def test_saves_checkpoint_data(self, mock_load, mock_save):
        """Should save checkpoint with correct fields."""
        mock_load.return_value = {"last_checkpoint": 0, "checkpoints": []}

        raw = {
            "tool_name": "Edit",
            "tool_input": {"file_path": "/test/file.py"},
            "cwd": "/test"
        }
        ctx = PreToolUseContext(raw)

        result = save_checkpoint_entry("session123", "/test/file.py", "test reason", ctx)

        self.assertEqual(result["session_id"], "session123")
        self.assertEqual(result["file"], "/test/file.py")
        self.assertEqual(result["reason"], "test reason")
        self.assertEqual(result["cwd"], "/test")
        self.assertIn("timestamp", result)

        # Verify save_state was called
        mock_save.assert_called_once()
        saved_state = mock_save.call_args[0][0]
        self.assertEqual(len(saved_state["checkpoints"]), 1)

    @patch('hooks.handlers.context_manager.save_state')
    @patch('hooks.handlers.context_manager.load_state')
    def test_limits_checkpoint_history(self, mock_load, mock_save):
        """Should keep only last 20 checkpoints."""
        # Create 25 old checkpoints
        old_checkpoints = [
            {"timestamp": f"2024-01-{i:02d}", "file": f"file{i}.py"}
            for i in range(1, 26)
        ]
        mock_load.return_value = {"last_checkpoint": 0, "checkpoints": old_checkpoints}

        raw = {
            "tool_name": "Edit",
            "tool_input": {"file_path": "/test/new.py"},
            "cwd": "/test"
        }
        ctx = PreToolUseContext(raw)

        save_checkpoint_entry("session123", "/test/new.py", "test", ctx)

        saved_state = mock_save.call_args[0][0]
        self.assertEqual(len(saved_state["checkpoints"]), 20)

    @patch('hooks.handlers.context_manager.save_state')
    @patch('hooks.handlers.context_manager.load_state')
    def test_updates_last_checkpoint_time(self, mock_load, mock_save):
        """Should update last_checkpoint timestamp."""
        mock_load.return_value = {"last_checkpoint": 0, "checkpoints": []}

        raw = {
            "tool_name": "Edit",
            "tool_input": {"file_path": "/test/file.py"},
            "cwd": "/test"
        }
        ctx = PreToolUseContext(raw)

        before = time.time()
        save_checkpoint_entry("session123", "/test/file.py", "test", ctx)
        after = time.time()

        saved_state = mock_save.call_args[0][0]
        self.assertGreaterEqual(saved_state["last_checkpoint"], before)
        self.assertLessEqual(saved_state["last_checkpoint"], after)


class TestHandlePreToolUse(TestCase):
    """Tests for handle_pre_tool_use function."""

    def setUp(self):
        """Clear checkpoint state before each test."""
        save_state({"last_checkpoint": 0, "checkpoints": []})

    def test_ignores_non_edit_tools(self):
        """Should return None for non-Edit/Write tools."""
        raw = {
            "tool_name": "Read",
            "tool_input": {"file_path": "/test/file.txt"},
            "session_id": "test123"
        }
        result = handle_pre_tool_use(raw)
        self.assertIsNone(result)

    def test_ignores_non_risky_edits(self):
        """Should return None for non-risky edits."""
        raw = {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": "/test/safe.py",
                "new_string": "print('hello')"
            },
            "session_id": "test123"
        }
        result = handle_pre_tool_use(raw)
        self.assertIsNone(result)

    @patch('hooks.handlers.context_manager.save_checkpoint_entry')
    @patch('hooks.handlers.context_manager.should_checkpoint')
    @patch('hooks.handlers.context_manager.is_risky_operation')
    def test_creates_checkpoint_for_risky_edit(self, mock_risky, mock_should, mock_save):
        """Should create checkpoint for risky edit when due."""
        mock_risky.return_value = (True, "test reason")
        mock_should.return_value = True
        mock_save.return_value = {
            "timestamp": "2024-01-01T12:00:00",
            "session_id": "test123",
            "file": "config.json",
            "reason": "test reason",
            "cwd": "/test"
        }

        raw = {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": "/test/config.json",
                "new_string": "risky content"
            },
            "session_id": "test123",
            "cwd": "/test"
        }

        result = handle_pre_tool_use(raw)

        self.assertIsNotNone(result)
        self.assertIn("hookSpecificOutput", result)
        self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "allow")
        self.assertIn("Checkpoint", result["hookSpecificOutput"]["permissionDecisionReason"])
        self.assertIn("config.json", result["hookSpecificOutput"]["permissionDecisionReason"])

    @patch('hooks.handlers.context_manager.should_checkpoint')
    @patch('hooks.handlers.context_manager.is_risky_operation')
    def test_skips_checkpoint_when_too_recent(self, mock_risky, mock_should):
        """Should skip checkpoint if last one was too recent."""
        mock_risky.return_value = (True, "test reason")
        mock_should.return_value = False

        raw = {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": "/test/config.json",
                "new_string": "risky content"
            },
            "session_id": "test123"
        }

        result = handle_pre_tool_use(raw)
        self.assertIsNone(result)

    def test_handles_write_tool(self):
        """Should handle Write tool same as Edit."""
        # Set old checkpoint time to allow new checkpoint
        save_state({"last_checkpoint": time.time() - 400, "checkpoints": []})

        # Use large content to trigger risky detection
        large_content = "x" * 600
        raw = {
            "tool_name": "Write",
            "tool_input": {
                "file_path": "/test/data.txt",
                "content": large_content
            },
            "session_id": "test123",
            "cwd": "/test"
        }

        result = handle_pre_tool_use(raw)
        self.assertIsNotNone(result)
        self.assertIn("hookSpecificOutput", result)
        self.assertIn("Checkpoint", result["hookSpecificOutput"]["permissionDecisionReason"])

    def test_handles_missing_file_path(self):
        """Should return None if file_path is missing."""
        raw = {
            "tool_name": "Edit",
            "tool_input": {},
            "session_id": "test123"
        }
        result = handle_pre_tool_use(raw)
        self.assertIsNone(result)


class TestHandlePostToolUse(TestCase):
    """Tests for handle_post_tool_use function."""

    def setUp(self):
        """Ensure error backup directory exists."""
        ERROR_BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        """Clean up error backups."""
        if ERROR_BACKUP_DIR.exists():
            for f in ERROR_BACKUP_DIR.glob("*.json"):
                f.unlink()

    def test_ignores_non_bash_tools(self):
        """Should return None for non-Bash tools."""
        raw = {
            "tool_name": "Read",
            "tool_input": {"file_path": "/test.txt"},
            "tool_result": {"content": "data"}
        }
        result = handle_post_tool_use(raw)
        self.assertIsNone(result)

    def test_ignores_successful_commands(self):
        """Should return None when exit_code is 0."""
        raw = {
            "tool_name": "Bash",
            "tool_input": {"command": "echo hello"},
            "tool_result": {"exit_code": 0, "output": "hello"}
        }
        result = handle_post_tool_use(raw)
        self.assertIsNone(result)

    def test_ignores_missing_exit_code(self):
        """Should return None when exit_code is None."""
        raw = {
            "tool_name": "Bash",
            "tool_input": {"command": "echo hello"},
            "tool_result": {"output": "hello"}
        }
        result = handle_post_tool_use(raw)
        self.assertIsNone(result)

    @patch('hooks.handlers.context_manager.save_error_backup')
    def test_saves_backup_on_error(self, mock_save):
        """Should save error backup when command fails."""
        mock_save.return_value = "/path/to/backup.json"

        raw = {
            "tool_name": "Bash",
            "tool_input": {"command": "false"},
            "tool_response": {"exit_code": 1, "stdout": "error message", "stderr": ""},
            "session_id": "test123",
            "cwd": "/test"
        }

        result = handle_post_tool_use(raw)

        mock_save.assert_called_once()
        call_args = mock_save.call_args[0]
        self.assertEqual(call_args[1], "false")
        self.assertEqual(call_args[2], 1)
        self.assertEqual(call_args[3], "error message")


class TestSaveErrorBackup(TestCase):
    """Tests for save_error_backup function."""

    def setUp(self):
        """Ensure error backup directory exists."""
        ERROR_BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        """Clean up error backups."""
        if ERROR_BACKUP_DIR.exists():
            for f in ERROR_BACKUP_DIR.glob("*.json"):
                f.unlink()

    def test_creates_backup_file(self):
        """Should create backup JSON file."""
        ctx = {"session_id": "test123", "cwd": "/test"}
        result = save_error_backup(ctx, "false", 1, "error output")

        self.assertIsNotNone(result)
        self.assertTrue(Path(result).exists())

        # Verify content
        with open(result) as f:
            data = json.load(f)

        self.assertEqual(data["session_id"], "test123")
        self.assertEqual(data["cwd"], "/test")
        self.assertEqual(data["command"], "false")
        self.assertEqual(data["exit_code"], 1)
        self.assertEqual(data["output"], "error output")

    def test_truncates_large_output(self):
        """Should truncate output over 10KB."""
        ctx = {"session_id": "test123", "cwd": "/test"}
        large_output = "x" * 15000
        result = save_error_backup(ctx, "cmd", 1, large_output)

        with open(result) as f:
            data = json.load(f)

        # Should be truncated to ~7000 chars (5000 + 2000 + truncation message)
        self.assertLess(len(data["output"]), 10000)
        self.assertIn("truncated", data["output"])

    def test_truncates_long_command(self):
        """Should truncate command over 500 chars."""
        ctx = {"session_id": "test123", "cwd": "/test"}
        long_cmd = "echo " + "x" * 600
        result = save_error_backup(ctx, long_cmd, 1, "output")

        with open(result) as f:
            data = json.load(f)

        self.assertEqual(len(data["command"]), 500)

    @patch('hooks.handlers.context_manager.rotate_error_backups')
    def test_rotates_backups(self, mock_rotate):
        """Should call rotate_error_backups after saving."""
        ctx = {"session_id": "test123", "cwd": "/test"}
        save_error_backup(ctx, "cmd", 1, "output")

        mock_rotate.assert_called_once()


class TestRotateErrorBackups(TestCase):
    """Tests for rotate_error_backups function."""

    def setUp(self):
        """Ensure error backup directory exists."""
        ERROR_BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        """Clean up error backups."""
        if ERROR_BACKUP_DIR.exists():
            for f in ERROR_BACKUP_DIR.glob("*.json"):
                f.unlink()

    def test_keeps_recent_backups(self):
        """Should keep backups under the limit."""
        # Create 10 backups (under limit of 20)
        for i in range(10):
            backup_file = ERROR_BACKUP_DIR / f"error_{i:03d}.json"
            backup_file.write_text('{}')
            time.sleep(0.01)  # Ensure different mtimes

        rotate_error_backups()

        remaining = list(ERROR_BACKUP_DIR.glob("*.json"))
        self.assertEqual(len(remaining), 10)

    def test_removes_oldest_backups(self):
        """Should remove oldest backups when over limit."""
        # Create 25 backups (over limit of 20)
        for i in range(25):
            backup_file = ERROR_BACKUP_DIR / f"error_{i:03d}.json"
            backup_file.write_text('{}')
            time.sleep(0.01)  # Ensure different mtimes

        rotate_error_backups()

        remaining = list(ERROR_BACKUP_DIR.glob("*.json"))
        self.assertEqual(len(remaining), 20)

        # Verify oldest ones are gone
        for i in range(5):
            self.assertFalse((ERROR_BACKUP_DIR / f"error_{i:03d}.json").exists())

    def test_handles_missing_directory(self):
        """Should not fail if directory doesn't exist."""
        # Remove directory
        for f in ERROR_BACKUP_DIR.glob("*.json"):
            f.unlink()
        ERROR_BACKUP_DIR.rmdir()

        # Should not raise
        rotate_error_backups()


class TestGetClaudeMdContent(TestCase):
    """Tests for get_claude_md_content function."""

    def test_returns_content_from_project_root(self):
        """Should read CLAUDE.md from project root."""
        with tempfile.TemporaryDirectory() as tmpdir:
            claude_md = Path(tmpdir) / "CLAUDE.md"
            claude_md.write_text("# Project Instructions\nTest content")

            result = get_claude_md_content(tmpdir)

            self.assertIn("Project CLAUDE.md preserved", result)
            self.assertIn("Test content", result)

    def test_returns_content_from_claude_dir(self):
        """Should read CLAUDE.md from .claude subdirectory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            claude_dir = Path(tmpdir) / ".claude"
            claude_dir.mkdir()
            claude_md = claude_dir / "CLAUDE.md"
            claude_md.write_text("# Config\nTest")

            result = get_claude_md_content(tmpdir)

            self.assertIn("Project CLAUDE.md preserved", result)
            self.assertIn("Test", result)

    def test_truncates_long_content(self):
        """Should truncate content to 2000 chars."""
        with tempfile.TemporaryDirectory() as tmpdir:
            claude_md = Path(tmpdir) / "CLAUDE.md"
            long_content = "x" * 3000
            claude_md.write_text(long_content)

            result = get_claude_md_content(tmpdir)

            # Should be truncated to 2000 chars plus the prefix
            content_part = result.split("\n", 1)[1]
            self.assertEqual(len(content_part), 2000)

    def test_returns_empty_when_missing(self):
        """Should return empty string if no CLAUDE.md found."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = get_claude_md_content(tmpdir)
            self.assertEqual(result, "")

    def test_prefers_root_over_subdirectory(self):
        """Should prefer root CLAUDE.md over .claude/ version."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create both
            claude_md_root = Path(tmpdir) / "CLAUDE.md"
            claude_md_root.write_text("ROOT")

            claude_dir = Path(tmpdir) / ".claude"
            claude_dir.mkdir()
            claude_md_sub = claude_dir / "CLAUDE.md"
            claude_md_sub.write_text("SUB")

            result = get_claude_md_content(tmpdir)

            self.assertIn("ROOT", result)
            self.assertNotIn("SUB", result)


class TestGetActiveTodos(TestCase):
    """Tests for get_active_todos function."""

    def test_returns_empty_when_no_todos(self):
        """Should return empty string when no todos in context."""
        ctx = {}
        result = get_active_todos(ctx)
        self.assertEqual(result, "")

    def test_returns_empty_when_todos_empty_list(self):
        """Should return empty string when todos list is empty."""
        ctx = {"todos": []}
        result = get_active_todos(ctx)
        self.assertEqual(result, "")

    def test_returns_pending_todos(self):
        """Should include pending todos."""
        ctx = {
            "todos": [
                {"status": "pending", "content": "Task 1"},
                {"status": "done", "content": "Task 2"}
            ]
        }
        result = get_active_todos(ctx)

        self.assertIn("Task 1", result)
        self.assertNotIn("Task 2", result)

    def test_returns_in_progress_todos(self):
        """Should include in-progress todos."""
        ctx = {
            "todos": [
                {"status": "in_progress", "content": "Working on it"},
                {"status": "done", "content": "Finished"}
            ]
        }
        result = get_active_todos(ctx)

        self.assertIn("Working on it", result)
        self.assertNotIn("Finished", result)

    def test_limits_to_10_todos(self):
        """Should limit output to 10 todos."""
        todos = [
            {"status": "pending", "content": f"Task {i}"}
            for i in range(20)
        ]
        ctx = {"todos": todos}
        result = get_active_todos(ctx)

        # Count bullet points
        lines = result.split("\n")
        todo_lines = [l for l in lines if l.strip().startswith("○")]
        self.assertEqual(len(todo_lines), 10)

    def test_uses_different_symbols(self):
        """Should use different symbols for pending vs in-progress."""
        ctx = {
            "todos": [
                {"status": "pending", "content": "Pending task"},
                {"status": "in_progress", "content": "Active task"}
            ]
        }
        result = get_active_todos(ctx)

        self.assertIn("○ Pending task", result)
        self.assertIn("→ Active task", result)


class TestGetKeyContext(TestCase):
    """Tests for get_key_context function."""

    def test_includes_session_id(self):
        """Should include session ID in context."""
        ctx = {"session_id": "test123456789", "cwd": "/test"}
        result = get_key_context(ctx)

        self.assertIn("[Session: test1234", result)

    def test_includes_cwd(self):
        """Should include working directory."""
        ctx = {"cwd": "/home/user/project", "session_id": "test"}
        result = get_key_context(ctx)

        self.assertIn("[Working directory: /home/user/project]", result)

    @patch('hooks.handlers.context_manager.get_claude_md_content')
    def test_includes_claude_md(self, mock_claude_md):
        """Should include CLAUDE.md content if present."""
        mock_claude_md.return_value = "[Project CLAUDE.md preserved]\nContent"
        ctx = {"cwd": "/test", "session_id": "test"}

        result = get_key_context(ctx)

        self.assertIn("Project CLAUDE.md preserved", result)

    @patch('hooks.handlers.context_manager.get_active_todos')
    def test_includes_todos(self, mock_todos):
        """Should include active todos if present."""
        mock_todos.return_value = "[Active Todos preserved]\n  ○ Task 1"
        ctx = {"cwd": "/test", "session_id": "test"}

        result = get_key_context(ctx)

        self.assertIn("Active Todos preserved", result)

    def test_separates_sections_with_blank_lines(self):
        """Should separate sections with blank lines."""
        ctx = {
            "cwd": "/test",
            "session_id": "test123"
        }
        result = get_key_context(ctx)

        # Should have double newlines between sections
        self.assertIn("\n\n", result)


class TestHandlePreCompact(TestCase):
    """Tests for handle_pre_compact function."""

    @patch('hooks.handlers.context_manager.update_session_state')
    @patch('hooks.handlers.context_manager.backup_transcript')
    def test_backs_up_transcript(self, mock_backup, mock_update):
        """Should backup transcript before compaction."""
        mock_backup.return_value = "/path/to/backup.md"

        ctx = {
            "transcript_path": "/path/to/transcript.md",
            "cwd": "/test",
            "session_id": "test123"
        }

        handle_pre_compact(ctx)

        mock_backup.assert_called_once_with("/path/to/transcript.md", reason="pre_compact")

    def test_returns_none_when_no_transcript_path(self):
        """Should return None if transcript_path is missing."""
        ctx = {"cwd": "/test"}
        result = handle_pre_compact(ctx)
        self.assertIsNone(result)

    @patch('hooks.handlers.context_manager.update_session_state')
    @patch('hooks.handlers.context_manager.backup_transcript')
    @patch('hooks.handlers.context_manager.get_key_context')
    def test_includes_key_context_in_message(self, mock_context, mock_backup, mock_update):
        """Should include key context in preservation message."""
        mock_backup.return_value = "/backup.md"
        mock_context.return_value = "[Working directory: /test]\n[Session: test123]"

        ctx = {
            "transcript_path": "/transcript.md",
            "cwd": "/test",
            "session_id": "test123"
        }

        result = handle_pre_compact(ctx)

        self.assertIsNotNone(result)
        self.assertEqual(result["result"], "continue")
        self.assertIn("Working directory", result["message"])

    @patch('hooks.handlers.context_manager.update_session_state')
    @patch('hooks.handlers.context_manager.backup_transcript')
    def test_includes_learning_reminder(self, mock_backup, mock_update):
        """Should include learning reminder in message."""
        mock_backup.return_value = "/backup.md"

        # Create learnings directory with sample files
        learnings_dir = Path.home() / ".claude/learnings"
        learnings_dir.mkdir(parents=True, exist_ok=True)
        (learnings_dir / "debugging.md").write_text("# Debug learnings")
        (learnings_dir / "testing.md").write_text("# Test learnings")

        try:
            ctx = {
                "transcript_path": "/transcript.md",
                "cwd": "/test",
                "session_id": "test123"
            }

            result = handle_pre_compact(ctx)

            self.assertIn("Learning Reminder", result["message"])
            self.assertIn("debugging", result["message"])
        finally:
            # Cleanup
            (learnings_dir / "debugging.md").unlink()
            (learnings_dir / "testing.md").unlink()


if __name__ == "__main__":
    main()

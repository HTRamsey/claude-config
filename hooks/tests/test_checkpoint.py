#!/usr/bin/env python3
"""Unit tests for checkpoint.py functions.

Tests for checkpoint management, risk detection, and error backup handling.
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
    load_state,
    save_state,
    is_risky_operation,
    should_checkpoint,
    save_checkpoint_entry,
    rotate_error_backups,
    save_error_backup,
    CHECKPOINT_INTERVAL,
    MAX_ERROR_BACKUPS,
)
from hooks.hook_sdk import PreToolUseContext


class TestLoadSaveState(TestCase):
    """Tests for load_state and save_state functions."""

    @patch("hooks.handlers.context_manager._checkpoint_state")
    def test_load_state_default(self, mock_state):
        """Loading state returns default structure."""
        mock_state.load.return_value = {"last_checkpoint": 0, "checkpoints": []}

        state = load_state()

        self.assertIn("last_checkpoint", state)
        self.assertIn("checkpoints", state)
        self.assertEqual(state["last_checkpoint"], 0)
        self.assertEqual(state["checkpoints"], [])
        mock_state.load.assert_called_once()

    @patch("hooks.handlers.context_manager._checkpoint_state")
    def test_load_state_existing(self, mock_state):
        """Loading state returns existing data."""
        existing_state = {
            "last_checkpoint": 1234567890.0,
            "checkpoints": [{"file": "test.py", "reason": "large edit"}]
        }
        mock_state.load.return_value = existing_state

        state = load_state()

        self.assertEqual(state["last_checkpoint"], 1234567890.0)
        self.assertEqual(len(state["checkpoints"]), 1)

    @patch("hooks.handlers.context_manager._checkpoint_state")
    def test_save_state(self, mock_state):
        """Saving state persists to storage."""
        state = {
            "last_checkpoint": time.time(),
            "checkpoints": [{"file": "test.py"}]
        }

        save_state(state)

        mock_state.save.assert_called_once_with(state)


class TestIsRiskyOperation(TestCase):
    """Tests for is_risky_operation function."""

    def test_config_file_not_risky(self):
        """Config files are NOT detected by current patterns (path patterns are for commands, not files)."""
        risky, reason = is_risky_operation("/etc/config.yml", "")
        self.assertFalse(risky)
        self.assertEqual(reason, "")

    def test_migration_file_not_risky(self):
        """Migration files are NOT detected by current patterns (path patterns are for commands, not files)."""
        risky, reason = is_risky_operation("/db/migrations/001_add_users.sql", "")
        self.assertFalse(risky)

    def test_detects_sql_keyword(self):
        """SQL keywords in content are risky."""
        risky, reason = is_risky_operation("/app/script.py", "DROP TABLE users;")
        self.assertTrue(risky)
        self.assertIn("drop", reason.lower())

    def test_detects_delete_keyword(self):
        """DELETE keyword is risky."""
        risky, reason = is_risky_operation("/app/cleanup.py", "os.remove(file_path)")
        self.assertTrue(risky)
        self.assertIn("remove", reason)

    def test_detects_large_edit(self):
        """Large edits (>500 chars) are risky."""
        large_content = "x" * 600
        risky, reason = is_risky_operation("/test/file.py", large_content)
        self.assertTrue(risky)
        self.assertIn("large edit", reason)

    def test_non_risky_operation(self):
        """Small, normal edits are not risky."""
        risky, reason = is_risky_operation("/test/file.py", "print('hello')")
        self.assertFalse(risky)
        self.assertEqual(reason, "")

    def test_case_insensitive_pattern_matching(self):
        """Pattern matching is case-insensitive for content keywords."""
        risky, reason = is_risky_operation("/app/script.py", "DELETE FROM users")
        self.assertTrue(risky)
        self.assertIn("delete", reason.lower())

    def test_case_insensitive_keyword_matching(self):
        """Keyword matching is case-insensitive."""
        risky, reason = is_risky_operation("/test.py", "DROP table users")
        self.assertTrue(risky)


class TestShouldCheckpoint(TestCase):
    """Tests for should_checkpoint function."""

    def test_should_checkpoint_after_interval(self):
        """Returns True if interval has passed."""
        old_time = time.time() - CHECKPOINT_INTERVAL - 10
        state = {"last_checkpoint": old_time}

        result = should_checkpoint(state)

        self.assertTrue(result)

    def test_should_not_checkpoint_before_interval(self):
        """Returns False if interval hasn't passed."""
        recent_time = time.time() - 10  # 10 seconds ago
        state = {"last_checkpoint": recent_time}

        result = should_checkpoint(state)

        self.assertFalse(result)

    def test_should_checkpoint_on_first_run(self):
        """Returns True if no previous checkpoint."""
        state = {"last_checkpoint": 0}

        result = should_checkpoint(state)

        self.assertTrue(result)


class TestSaveCheckpointEntry(TestCase):
    """Tests for save_checkpoint_entry function."""

    @patch("hooks.handlers.context_manager.load_state")
    @patch("hooks.handlers.context_manager.save_state")
    def test_saves_checkpoint_entry(self, mock_save, mock_load):
        """Saves checkpoint entry with all details."""
        mock_load.return_value = {"last_checkpoint": 0, "checkpoints": []}

        raw = {
            "tool_name": "Edit",
            "tool_input": {"file_path": "/test/file.py"},
            "cwd": "/project"
        }
        ctx = PreToolUseContext(raw)

        checkpoint = save_checkpoint_entry("test-session", "/test/file.py", "large edit", ctx)

        self.assertEqual(checkpoint["session_id"], "test-session")
        self.assertEqual(checkpoint["file"], "/test/file.py")
        self.assertEqual(checkpoint["reason"], "large edit")
        self.assertEqual(checkpoint["cwd"], "/project")
        self.assertIn("timestamp", checkpoint)

    @patch("hooks.handlers.context_manager.load_state")
    @patch("hooks.handlers.context_manager.save_state")
    def test_updates_last_checkpoint_time(self, mock_save, mock_load):
        """Updates last_checkpoint timestamp in state."""
        mock_load.return_value = {"last_checkpoint": 0, "checkpoints": []}

        raw = {
            "tool_name": "Edit",
            "tool_input": {"file_path": "/test/file.py"},
            "cwd": "/project"
        }
        ctx = PreToolUseContext(raw)

        before = time.time()
        save_checkpoint_entry("test-session", "/test/file.py", "large edit", ctx)
        after = time.time()

        # Check that state was saved with updated timestamp
        saved_state = mock_save.call_args[0][0]
        self.assertGreaterEqual(saved_state["last_checkpoint"], before)
        self.assertLessEqual(saved_state["last_checkpoint"], after)

    @patch("hooks.handlers.context_manager.load_state")
    @patch("hooks.handlers.context_manager.save_state")
    def test_limits_checkpoints_to_20(self, mock_save, mock_load):
        """Keeps only last 20 checkpoints."""
        existing_checkpoints = [
            {"file": f"file{i}.py", "timestamp": datetime.now().isoformat()}
            for i in range(25)
        ]
        mock_load.return_value = {
            "last_checkpoint": 0,
            "checkpoints": existing_checkpoints
        }

        raw = {
            "tool_name": "Edit",
            "tool_input": {"file_path": "/test/new.py"},
            "cwd": "/project"
        }
        ctx = PreToolUseContext(raw)

        save_checkpoint_entry("test-session", "/test/new.py", "large edit", ctx)

        saved_state = mock_save.call_args[0][0]
        self.assertEqual(len(saved_state["checkpoints"]), 20)


class TestRotateErrorBackups(TestCase):
    """Tests for rotate_error_backups function."""

    def test_keeps_recent_backups_under_limit(self):
        """Keeps backups when under MAX_ERROR_BACKUPS."""
        with tempfile.TemporaryDirectory() as tmpdir:
            backup_dir = Path(tmpdir)

            # Create fewer backups than limit
            for i in range(MAX_ERROR_BACKUPS - 2):
                backup = backup_dir / f"error_{i}.json"
                backup.write_text(json.dumps({"error": i}))

            with patch("hooks.handlers.context_manager.ERROR_BACKUP_DIR", backup_dir):
                rotate_error_backups()

            # All should remain
            remaining = list(backup_dir.glob("*.json"))
            self.assertEqual(len(remaining), MAX_ERROR_BACKUPS - 2)

    def test_deletes_oldest_backups_over_limit(self):
        """Deletes oldest backups when over MAX_ERROR_BACKUPS."""
        with tempfile.TemporaryDirectory() as tmpdir:
            backup_dir = Path(tmpdir)

            # Create more backups than limit
            for i in range(MAX_ERROR_BACKUPS + 5):
                backup = backup_dir / f"error_{i:03d}.json"
                backup.write_text(json.dumps({"error": i}))
                # Add small delay to ensure different mtimes
                time.sleep(0.01)

            with patch("hooks.handlers.context_manager.ERROR_BACKUP_DIR", backup_dir):
                rotate_error_backups()

            # Should only keep MAX_ERROR_BACKUPS
            remaining = list(backup_dir.glob("*.json"))
            self.assertEqual(len(remaining), MAX_ERROR_BACKUPS)

            # Oldest ones should be deleted
            remaining_names = {f.name for f in remaining}
            self.assertNotIn("error_000.json", remaining_names)
            self.assertNotIn("error_001.json", remaining_names)

    def test_handles_missing_directory(self):
        """Handles missing backup directory gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            nonexistent_dir = Path(tmpdir) / "nonexistent"

            with patch("hooks.handlers.context_manager.ERROR_BACKUP_DIR", nonexistent_dir):
                # Should not raise exception
                rotate_error_backups()

    def test_handles_permission_error(self):
        """Handles permission errors gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            backup_dir = Path(tmpdir)

            # Create backups
            backups = []
            for i in range(MAX_ERROR_BACKUPS + 2):
                backup = backup_dir / f"error_{i}.json"
                backup.write_text(json.dumps({"error": i}))
                backups.append(backup)

            # Make oldest backup undeletable (simulate permission error)
            oldest = backups[0]
            with patch.object(Path, "unlink", side_effect=PermissionError):
                with patch("hooks.handlers.context_manager.ERROR_BACKUP_DIR", backup_dir):
                    # Should not raise exception
                    rotate_error_backups()


class TestSaveErrorBackup(TestCase):
    """Tests for save_error_backup function."""

    def test_saves_error_backup(self):
        """Saves error backup with all context."""
        with tempfile.TemporaryDirectory() as tmpdir:
            backup_dir = Path(tmpdir)

            with patch("hooks.handlers.context_manager.ERROR_BACKUP_DIR", backup_dir):
                raw = {
                    "session_id": "test-session",
                    "cwd": "/project"
                }

                result = save_error_backup(raw, "make test", 1, "Error: build failed")

            self.assertIsNotNone(result)
            self.assertTrue(Path(result).exists())

            # Verify backup contents
            with open(result) as f:
                data = json.load(f)

            self.assertEqual(data["session_id"], "test-session")
            self.assertEqual(data["cwd"], "/project")
            self.assertEqual(data["command"], "make test")
            self.assertEqual(data["exit_code"], 1)
            self.assertEqual(data["output"], "Error: build failed")
            self.assertIn("timestamp", data)

    def test_truncates_long_output(self):
        """Truncates output over 10000 chars."""
        with tempfile.TemporaryDirectory() as tmpdir:
            backup_dir = Path(tmpdir)

            with patch("hooks.handlers.context_manager.ERROR_BACKUP_DIR", backup_dir):
                raw = {"session_id": "test", "cwd": "/project"}
                long_output = "x" * 20000

                result = save_error_backup(raw, "test", 1, long_output)

            with open(result) as f:
                data = json.load(f)

            # Should be truncated: 5000 + middle + 2000 + markers
            self.assertLess(len(data["output"]), 10000)
            self.assertIn("[truncated]", data["output"])

    def test_truncates_long_command(self):
        """Truncates command over 500 chars."""
        with tempfile.TemporaryDirectory() as tmpdir:
            backup_dir = Path(tmpdir)

            with patch("hooks.handlers.context_manager.ERROR_BACKUP_DIR", backup_dir):
                raw = {"session_id": "test", "cwd": "/project"}
                long_command = "python script.py " + " ".join([f"arg{i}" for i in range(200)])

                result = save_error_backup(raw, long_command, 1, "error")

            with open(result) as f:
                data = json.load(f)

            # Should be truncated to 500 chars
            self.assertEqual(len(data["command"]), 500)

    def test_creates_directory_if_missing(self):
        """Creates backup directory if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            backup_dir = Path(tmpdir) / "backups"

            with patch("hooks.handlers.context_manager.ERROR_BACKUP_DIR", backup_dir):
                raw = {"session_id": "test", "cwd": "/project"}

                result = save_error_backup(raw, "test", 1, "error")

            self.assertTrue(backup_dir.exists())
            self.assertTrue(Path(result).exists())


    def test_handles_save_error_gracefully(self):
        """Returns None if save fails."""
        with tempfile.TemporaryDirectory() as tmpdir:
            backup_dir = Path(tmpdir) / "readonly"
            backup_dir.mkdir()
            backup_dir.chmod(0o444)  # Read-only

            with patch("hooks.handlers.context_manager.ERROR_BACKUP_DIR", backup_dir):
                raw = {"session_id": "test", "cwd": "/project"}

                result = save_error_backup(raw, "test", 1, "error")

                # Should return None on error
                self.assertIsNone(result)

            # Cleanup
            backup_dir.chmod(0o755)

    def test_uses_unknown_for_missing_session_id(self):
        """Uses 'unknown' for missing session_id."""
        with tempfile.TemporaryDirectory() as tmpdir:
            backup_dir = Path(tmpdir)

            with patch("hooks.handlers.context_manager.ERROR_BACKUP_DIR", backup_dir):
                raw = {"cwd": "/project"}  # No session_id

                result = save_error_backup(raw, "test", 1, "error")

            with open(result) as f:
                data = json.load(f)

            self.assertEqual(data["session_id"], "unknown")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Unit tests for hook_utils.py core functions."""

import json
import os
import sys
import tempfile
import time
from pathlib import Path
from unittest import TestCase, main
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))
from hook_utils import (
    get_session_id,
    log_event,
    is_hook_disabled,
    atomic_write_json,
    read_state,
    write_state,
    file_lock,
    safe_load_json,
    safe_save_json,
)


class TestGetSessionId(TestCase):
    """Tests for get_session_id function."""

    def test_returns_string(self):
        """Should always return a string."""
        result = get_session_id()
        self.assertIsInstance(result, str)
        self.assertTrue(len(result) > 0)

    def test_env_var_override(self):
        """CLAUDE_SESSION_ID env var should be used if set."""
        with patch.dict(os.environ, {"CLAUDE_SESSION_ID": "test-session-123"}):
            result = get_session_id()
            self.assertEqual(result, "test-session-123")


class TestLogEvent(TestCase):
    """Tests for log_event function."""

    def test_log_event_no_crash(self):
        """Log event should not crash on any input."""
        # Should not raise
        log_event("test_hook", "test_event", {"key": "value"})
        log_event("test_hook", "test_event", None)
        log_event("test_hook", "test_event", {"nested": {"data": [1, 2, 3]}})

    def test_log_event_with_level(self):
        """Log event should accept level parameter."""
        log_event("test_hook", "test_event", {"key": "value"}, level="error")
        log_event("test_hook", "test_event", {"key": "value"}, level="warn")


class TestIsHookDisabled(TestCase):
    """Tests for is_hook_disabled function."""

    def test_returns_boolean(self):
        """Should return boolean."""
        result = is_hook_disabled("some_hook")
        self.assertIsInstance(result, bool)

    def test_nonexistent_hook_not_disabled(self):
        """Hooks not in config should not be disabled."""
        result = is_hook_disabled("definitely_not_configured_hook_xyz")
        self.assertFalse(result)


class TestAtomicWriteJson(TestCase):
    """Tests for atomic_write_json function."""

    def test_writes_valid_json(self):
        """Should write valid JSON that can be read back."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.json"

            data = {"key": "value", "number": 42, "list": [1, 2, 3]}
            result = atomic_write_json(path, data)

            self.assertTrue(result)

            with open(path) as f:
                loaded = json.load(f)

            self.assertEqual(loaded, data)

    def test_returns_false_on_error(self):
        """Should return False on write error."""
        # Try to write to invalid path
        result = atomic_write_json(Path("/nonexistent/path/file.json"), {"data": "test"})
        self.assertFalse(result)


class TestReadWriteState(TestCase):
    """Tests for read_state and write_state functions."""

    def test_read_nonexistent_returns_default(self):
        """Reading nonexistent state should return default."""
        result = read_state("definitely_nonexistent_state_xyz", default={"default": "value"})
        self.assertEqual(result, {"default": "value"})

    def test_read_state_returns_dict(self):
        """Read state should always return a dict."""
        result = read_state("some_state", default={})
        self.assertIsInstance(result, dict)


class TestFileLock(TestCase):
    """Tests for file_lock context manager."""

    def test_lock_and_unlock(self):
        """Lock should be acquired and released."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            path = f.name

        try:
            with open(path, 'r+') as f:
                with file_lock(f):
                    # Should be able to write while locked
                    f.write("test")
                # Lock released after context

            # File should be readable after
            with open(path) as f:
                content = f.read()
                self.assertIn("test", content)
        finally:
            os.unlink(path)


class TestGracefulMain(TestCase):
    """Tests for graceful_main decorator."""

    def test_decorator_catches_exceptions(self):
        """Decorated function should exit(0) on error, not raise."""
        from hook_utils import graceful_main

        @graceful_main("test_hook")
        def failing_function():
            raise ValueError("Test error")

        # Should call sys.exit(0), which we catch as SystemExit
        with self.assertRaises(SystemExit) as cm:
            failing_function()
        self.assertEqual(cm.exception.code, 0)

    def test_decorator_preserves_return(self):
        """Decorated function should return normally on success."""
        from hook_utils import graceful_main

        @graceful_main("test_hook")
        def successful_function():
            return "success"

        result = successful_function()
        self.assertEqual(result, "success")


if __name__ == "__main__":
    main()

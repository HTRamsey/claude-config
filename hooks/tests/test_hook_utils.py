"""Tests for hook_utils package."""
import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from hooks.hook_utils import (
    file_lock, safe_load_json, atomic_write_json,
    log_event, graceful_main, DATA_DIR,
    read_state, write_state,
    get_session_id, read_session_state, write_session_state,
    is_hook_disabled, record_usage,
)
import hooks.hook_utils.hooks as hooks_module


class TestIO:
    """Tests for hook_utils.io module."""

    def test_file_lock_context_manager(self, tmp_path):
        """file_lock should work as context manager with file handle."""
        test_file = tmp_path / "test.lock"
        with open(test_file, "w") as f:
            with file_lock(f):
                f.write("test")
        assert test_file.exists()
        assert test_file.read_text() == "test"

    def test_safe_load_json_valid(self, tmp_path):
        """safe_load_json should load valid JSON."""
        test_file = tmp_path / "test.json"
        test_file.write_text('{"key": "value"}')
        result = safe_load_json(test_file)  # Takes Path, not string
        assert result == {"key": "value"}

    def test_safe_load_json_missing(self, tmp_path):
        """safe_load_json should return default for missing file."""
        result = safe_load_json(tmp_path / "missing.json", {"default": True})
        assert result == {"default": True}

    def test_safe_load_json_invalid(self, tmp_path):
        """safe_load_json should return default for invalid JSON."""
        test_file = tmp_path / "invalid.json"
        test_file.write_text("not json")
        result = safe_load_json(test_file, {"fallback": True})
        assert result == {"fallback": True}

    def test_atomic_write_json(self, tmp_path):
        """atomic_write_json should write atomically."""
        test_file = tmp_path / "test.json"
        atomic_write_json(test_file, {"hello": "world"})  # Takes Path
        assert test_file.exists()
        content = json.loads(test_file.read_text())
        assert content == {"hello": "world"}


class TestState:
    """Tests for hook_utils.state module."""

    def test_read_write_state_roundtrip(self, tmp_path):
        """State should roundtrip through read/write."""
        with patch('hooks.hook_utils.state.DATA_DIR', tmp_path):
            write_state("test_key", {"data": 123})
            result = read_state("test_key")
            assert result == {"data": 123}

    def test_read_state_default(self, tmp_path):
        """read_state should return default for missing key."""
        with patch('hooks.hook_utils.state.DATA_DIR', tmp_path):
            result = read_state("missing_key", {"default": True})
            assert result == {"default": True}


class TestSession:
    """Tests for hook_utils.session module."""

    def test_get_session_id_from_env(self):
        """get_session_id should read from environment."""
        with patch.dict(os.environ, {"CLAUDE_SESSION_ID": "test-session-123"}):
            session_id = get_session_id()
            assert session_id == "test-session-123"

    def test_get_session_id_fallback(self):
        """get_session_id should return 'default' when not set."""
        env = os.environ.copy()
        env.pop("CLAUDE_SESSION_ID", None)
        with patch.dict(os.environ, env, clear=True):
            session_id = get_session_id()
            assert session_id == "default"


class TestHooks:
    """Tests for hook_utils.hooks module."""

    def test_is_hook_disabled_when_not_disabled(self, tmp_path):
        """is_hook_disabled returns False when hook not in disabled list."""
        config_file = tmp_path / "hook-config.json"
        config_file.write_text('{"disabled": ["other_hook"]}')
        # Clear cache and patch DATA_DIR
        hooks_module._hook_disabled_cache.clear()
        with patch.object(hooks_module, 'DATA_DIR', tmp_path):
            result = hooks_module.is_hook_disabled("unique_hook_1")
            assert result is False

    def test_is_hook_disabled_when_disabled(self, tmp_path):
        """is_hook_disabled returns True when hook in disabled list."""
        config_file = tmp_path / "hook-config.json"
        config_file.write_text('{"disabled": ["unique_hook_2"]}')
        # Clear cache and patch DATA_DIR
        hooks_module._hook_disabled_cache.clear()
        with patch.object(hooks_module, 'DATA_DIR', tmp_path):
            result = hooks_module.is_hook_disabled("unique_hook_2")
            assert result is True


class TestGracefulMain:
    """Tests for graceful_main decorator."""

    def test_graceful_main_success(self):
        """graceful_main should allow normal execution."""
        @graceful_main("test_hook")
        def test_func():
            return "success"

        result = test_func()
        assert result == "success"

    def test_graceful_main_catches_exceptions(self):
        """graceful_main should catch exceptions and exit gracefully."""
        @graceful_main("test_hook")
        def failing_func():
            raise ValueError("test error")

        with pytest.raises(SystemExit) as exc_info:
            failing_func()
        assert exc_info.value.code == 0

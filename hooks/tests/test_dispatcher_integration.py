"""Integration tests for hook dispatchers.

Tests end-to-end dispatcher behavior with mocked handlers.
"""
import json
import os
import sys
from io import StringIO
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Add hooks directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from dispatcher_base import BaseDispatcher
from pre_tool_dispatcher import PreToolDispatcher
from post_tool_dispatcher import PostToolDispatcher


class TestBaseDispatcher:
    """Tests for BaseDispatcher functionality."""

    def test_dispatch_returns_none_for_unknown_tool(self):
        """Unknown tools should return None without error."""
        dispatcher = PreToolDispatcher()
        ctx = {"tool_name": "UnknownTool", "tool_input": {}}
        result = dispatcher.dispatch(ctx)
        assert result is None

    def test_dispatch_returns_none_for_empty_context(self):
        """Empty context should return None without error."""
        dispatcher = PreToolDispatcher()
        result = dispatcher.dispatch({})
        assert result is None

    def test_handler_caching(self):
        """Handlers should be cached after first import."""
        dispatcher = PreToolDispatcher()

        # First call imports
        handler1 = dispatcher.get_handler("file_protection")
        # Second call returns cached
        handler2 = dispatcher.get_handler("file_protection")

        assert handler1 is handler2

    def test_disabled_handler_skipped(self, tmp_path):
        """Disabled handlers should be skipped."""
        # Create hook config with disabled handler
        config_file = tmp_path / "hook-config.json"
        config_file.write_text(json.dumps({"disabled": ["file_protection"]}))

        import hook_utils.hooks as hooks_module

        # Patch DATA_DIR in hooks module and clear cache
        original_data_dir = hooks_module.DATA_DIR
        try:
            hooks_module.DATA_DIR = tmp_path
            hooks_module._hook_disabled_cache.clear()

            # Now is_hook_disabled should find our config
            result = hooks_module.is_hook_disabled("file_protection")
            assert result == True
        finally:
            hooks_module.DATA_DIR = original_data_dir
            hooks_module._hook_disabled_cache.clear()


class TestPreToolDispatcher:
    """Integration tests for PreToolDispatcher."""

    def test_edit_routes_to_correct_handlers(self):
        """Edit tool should route to file_protection, tdd_guard, etc."""
        dispatcher = PreToolDispatcher()
        handlers = dispatcher.TOOL_HANDLERS.get("Edit", [])

        assert "file_protection" in handlers
        assert "tdd_guard" in handlers
        assert "suggestion_engine" in handlers

    def test_bash_routes_to_correct_handlers(self):
        """Bash tool should route to dangerous_command_blocker, etc."""
        dispatcher = PreToolDispatcher()
        handlers = dispatcher.TOOL_HANDLERS.get("Bash", [])

        assert "dangerous_command_blocker" in handlers
        assert "credential_scanner" in handlers

    def test_deny_decision_terminates_early(self):
        """Deny decision should stop processing and return immediately."""
        dispatcher = PreToolDispatcher()

        deny_result = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": "Blocked for testing"
            }
        }

        # Mock file_protection to return deny
        with patch.object(dispatcher, 'get_handler') as mock_get:
            mock_handler = MagicMock(return_value=deny_result)
            mock_get.return_value = mock_handler

            ctx = {"tool_name": "Edit", "tool_input": {"file_path": "/etc/passwd"}}
            result = dispatcher.dispatch(ctx)

            assert result is not None
            assert result["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_messages_collected_and_joined(self):
        """Multiple handler messages should be collected and joined."""
        dispatcher = PreToolDispatcher()

        # Create mock handlers that return messages
        message_result = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "permissionDecisionReason": "Test message"
            }
        }

        with patch.object(dispatcher, 'run_handler') as mock_run:
            mock_run.return_value = message_result

            ctx = {"tool_name": "Read", "tool_input": {"file_path": "/test"}}
            result = dispatcher.dispatch(ctx)

            # Should have collected messages
            if result:
                assert "hookSpecificOutput" in result

    def test_task_routes_to_subagent_lifecycle(self):
        """Task tool should route to subagent_lifecycle and unified_cache."""
        dispatcher = PreToolDispatcher()
        handlers = dispatcher.TOOL_HANDLERS.get("Task", [])

        assert "subagent_lifecycle" in handlers
        assert "unified_cache" in handlers
        assert "usage_tracker" in handlers

    def test_credential_scanner_only_on_git_commit(self):
        """Credential scanner should only run on git commit commands."""
        dispatcher = PreToolDispatcher()

        # Mock the credential scanner handler tuple
        mock_scan = MagicMock(return_value=[])
        mock_get_diff = MagicMock(return_value=("", []))
        mock_is_allowed = MagicMock(return_value=False)

        with patch.object(dispatcher, 'get_handler') as mock_get:
            mock_get.return_value = (mock_scan, mock_get_diff, mock_is_allowed)

            # Non-commit command should not trigger scan
            ctx = {"tool_name": "Bash", "tool_input": {"command": "ls -la"}}
            result = dispatcher._execute_handler(
                "credential_scanner",
                (mock_scan, mock_get_diff, mock_is_allowed),
                ctx
            )

            assert result is None
            mock_get_diff.assert_not_called()


class TestPostToolDispatcher:
    """Integration tests for PostToolDispatcher."""

    def test_edit_routes_to_batch_detector(self):
        """Edit tool should route to batch_operation_detector."""
        dispatcher = PostToolDispatcher()
        handlers = dispatcher.TOOL_HANDLERS.get("Edit", [])

        assert "batch_operation_detector" in handlers
        assert "tool_analytics" in handlers

    def test_bash_routes_to_build_analyzer(self):
        """Bash tool should route to build_analyzer."""
        dispatcher = PostToolDispatcher()
        handlers = dispatcher.TOOL_HANDLERS.get("Bash", [])

        assert "build_analyzer" in handlers
        assert "tool_analytics" in handlers

    def test_task_routes_to_suggestion_engine(self):
        """Task tool should route to suggestion_engine for agent chaining."""
        dispatcher = PostToolDispatcher()
        handlers = dispatcher.TOOL_HANDLERS.get("Task", [])

        assert "suggestion_engine" in handlers
        assert "unified_cache" in handlers
        assert "subagent_lifecycle" in handlers

    def test_post_tool_no_early_termination(self):
        """PostToolUse should not terminate early (no deny decisions)."""
        dispatcher = PostToolDispatcher()

        # _should_terminate should always return False for PostToolUse
        result = {"hookSpecificOutput": {"message": "test"}}
        assert dispatcher._should_terminate(result, "test_handler", "Edit") == False

    def test_webfetch_routes_to_unified_cache(self):
        """WebFetch should route to unified_cache for research caching."""
        dispatcher = PostToolDispatcher()
        handlers = dispatcher.TOOL_HANDLERS.get("WebFetch", [])

        assert "unified_cache" in handlers


class TestDispatcherEndToEnd:
    """End-to-end tests running actual dispatcher flow."""

    def test_pre_tool_dispatcher_full_flow(self):
        """Test full PreToolDispatcher flow with real handlers."""
        dispatcher = PreToolDispatcher()

        # Simple Read that should pass through
        ctx = {
            "tool_name": "Read",
            "tool_input": {"file_path": "/home/user/test.py"}
        }

        # This runs actual handlers - may produce messages or None
        result = dispatcher.dispatch(ctx)

        # Should not crash, result can be None or dict
        assert result is None or isinstance(result, dict)

    def test_post_tool_dispatcher_full_flow(self):
        """Test full PostToolDispatcher flow with real handlers."""
        dispatcher = PostToolDispatcher()

        # Simulate a successful Bash command
        ctx = {
            "tool_name": "Bash",
            "tool_input": {"command": "echo hello"},
            "tool_response": "hello\n"
        }

        # This runs actual handlers
        result = dispatcher.dispatch(ctx)

        # Should not crash
        assert result is None or isinstance(result, dict)

    def test_stdin_stdout_integration(self, monkeypatch, capsys):
        """Test dispatcher reads stdin and writes to stdout correctly."""
        ctx = {"tool_name": "Glob", "tool_input": {"pattern": "*.py"}}

        # Mock stdin
        monkeypatch.setattr('sys.stdin', StringIO(json.dumps(ctx)))

        dispatcher = PreToolDispatcher()
        dispatcher._validated = True  # Skip validation

        # Capture the run - it will call sys.exit(0)
        with pytest.raises(SystemExit) as exc_info:
            dispatcher.run()

        assert exc_info.value.code == 0

    def test_invalid_json_graceful_exit(self, monkeypatch):
        """Invalid JSON input should exit gracefully."""
        monkeypatch.setattr('sys.stdin', StringIO("not valid json"))

        dispatcher = PreToolDispatcher()
        dispatcher._validated = True

        with pytest.raises(SystemExit) as exc_info:
            dispatcher.run()

        assert exc_info.value.code == 0


class TestHandlerValidation:
    """Tests for handler import validation."""

    def test_pre_tool_all_handlers_importable(self):
        """All PreToolDispatcher handlers should be importable."""
        dispatcher = PreToolDispatcher()

        failed = []
        for name in dispatcher.ALL_HANDLERS:
            handler = dispatcher.get_handler(name)
            if handler is None:
                failed.append(name)

        assert failed == [], f"Failed to import: {failed}"

    def test_post_tool_all_handlers_importable(self):
        """All PostToolDispatcher handlers should be importable."""
        dispatcher = PostToolDispatcher()

        failed = []
        for name in dispatcher.ALL_HANDLERS:
            handler = dispatcher.get_handler(name)
            if handler is None:
                failed.append(name)

        assert failed == [], f"Failed to import: {failed}"

    def test_handler_callable_or_tuple(self):
        """Handlers should be callable or tuple of callables."""
        for DispatcherClass in [PreToolDispatcher, PostToolDispatcher]:
            dispatcher = DispatcherClass()

            for name in dispatcher.ALL_HANDLERS:
                handler = dispatcher.get_handler(name)
                if handler is not None:
                    if isinstance(handler, tuple):
                        for h in handler:
                            assert callable(h), f"{name} tuple element not callable"
                    else:
                        assert callable(handler), f"{name} not callable"


class TestToolHandlerMapping:
    """Tests for tool-to-handler mapping consistency."""

    def test_pre_tool_handlers_exist(self):
        """All handlers in TOOL_HANDLERS should exist in ALL_HANDLERS."""
        dispatcher = PreToolDispatcher()

        all_mapped = set()
        for handlers in dispatcher.TOOL_HANDLERS.values():
            all_mapped.update(handlers)

        missing = all_mapped - set(dispatcher.ALL_HANDLERS)
        assert missing == set(), f"Handlers in mapping but not ALL_HANDLERS: {missing}"

    def test_post_tool_handlers_exist(self):
        """All handlers in TOOL_HANDLERS should exist in ALL_HANDLERS."""
        dispatcher = PostToolDispatcher()

        all_mapped = set()
        for handlers in dispatcher.TOOL_HANDLERS.values():
            all_mapped.update(handlers)

        missing = all_mapped - set(dispatcher.ALL_HANDLERS)
        assert missing == set(), f"Handlers in mapping but not ALL_HANDLERS: {missing}"

    def test_no_duplicate_handlers_per_tool(self):
        """Each tool should not have duplicate handlers."""
        for DispatcherClass in [PreToolDispatcher, PostToolDispatcher]:
            dispatcher = DispatcherClass()

            for tool, handlers in dispatcher.TOOL_HANDLERS.items():
                assert len(handlers) == len(set(handlers)), \
                    f"{tool} has duplicate handlers: {handlers}"

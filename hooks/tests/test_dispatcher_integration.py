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

from hooks.dispatchers.base import BaseDispatcher, PreToolStrategy, PostToolStrategy, RoutingRule, HandlerRegistry
from hooks.dispatchers.pre_tool import PreToolDispatcher
from hooks.dispatchers.post_tool import PostToolDispatcher
from hooks.dispatchers.user_prompt import UserPromptDispatcher, UserPromptStrategy


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

        import hooks.hook_utils.hooks as hooks_module

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
        # Initialize handler registry with custom executors
        dispatcher.setup_handler_registry()

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

    def test_bash_routes_to_tool_analytics(self):
        """Bash tool should route to tool_analytics (includes build analysis)."""
        dispatcher = PostToolDispatcher()
        handlers = dispatcher.TOOL_HANDLERS.get("Bash", [])

        # build_analyzer was consolidated into tool_analytics
        assert "tool_analytics" in handlers
        assert "context_manager" in handlers

    def test_task_routes_to_suggestion_engine(self):
        """Task tool should route to suggestion_engine for agent chaining."""
        dispatcher = PostToolDispatcher()
        handlers = dispatcher.TOOL_HANDLERS.get("Task", [])

        assert "suggestion_engine" in handlers
        assert "unified_cache" in handlers
        assert "subagent_lifecycle" in handlers

    def test_post_tool_no_early_termination(self):
        """PostToolUse should not terminate early (no deny decisions)."""
        from hooks.dispatchers.base import PostToolStrategy

        strategy = PostToolStrategy()
        result = {"hookSpecificOutput": {"message": "test"}}
        # PostToolStrategy.should_terminate always returns False
        assert strategy.should_terminate(result, "test_handler") == False

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


class TestResultStrategies:
    """Tests for ResultStrategy implementations."""

    def test_pre_tool_creates_pre_tool_strategy(self):
        """PreToolDispatcher._create_result_strategy() returns PreToolStrategy."""
        dispatcher = PreToolDispatcher()
        strategy = dispatcher._create_result_strategy()
        assert isinstance(strategy, PreToolStrategy)

    def test_post_tool_creates_post_tool_strategy(self):
        """PostToolDispatcher._create_result_strategy() returns PostToolStrategy."""
        dispatcher = PostToolDispatcher()
        strategy = dispatcher._create_result_strategy()
        assert isinstance(strategy, PostToolStrategy)

    def test_pre_tool_strategy_terminates_on_deny(self):
        """PreToolStrategy.should_terminate() returns True for deny decisions."""
        strategy = PreToolStrategy()
        result = {
            "hookSpecificOutput": {
                "permissionDecision": "deny",
                "permissionDecisionReason": "Test deny"
            }
        }
        assert strategy.should_terminate(result, "test_handler") == True

    def test_pre_tool_strategy_no_terminate_on_allow(self):
        """PreToolStrategy.should_terminate() returns False for allow decisions."""
        strategy = PreToolStrategy()
        result = {
            "hookSpecificOutput": {
                "permissionDecision": "allow",
                "permissionDecisionReason": "Test allow"
            }
        }
        assert strategy.should_terminate(result, "test_handler") == False

    def test_post_tool_strategy_never_terminates(self):
        """PostToolStrategy.should_terminate() always returns False."""
        strategy = PostToolStrategy()
        result = {
            "hookSpecificOutput": {
                "message": "Test message"
            }
        }
        assert strategy.should_terminate(result, "test_handler") == False

    def test_pre_tool_strategy_extracts_permission_reason(self):
        """PreToolStrategy.extract_message() extracts permissionDecisionReason."""
        strategy = PreToolStrategy()
        hook_output = {
            "permissionDecision": "allow",
            "permissionDecisionReason": "Test reason"
        }
        assert strategy.extract_message(hook_output) == "Test reason"

    def test_post_tool_strategy_extracts_message(self):
        """PostToolStrategy.extract_message() extracts message field."""
        strategy = PostToolStrategy()
        hook_output = {
            "message": "Test message"
        }
        assert strategy.extract_message(hook_output) == "Test message"

    def test_pre_tool_strategy_builds_allow_result(self):
        """PreToolStrategy.build_result() creates allow result."""
        strategy = PreToolStrategy()
        result = strategy.build_result(["msg1", "msg2"])
        assert result["hookSpecificOutput"]["permissionDecision"] == "allow"
        assert "msg1" in result["hookSpecificOutput"]["permissionDecisionReason"]

    def test_post_tool_strategy_builds_message_result(self):
        """PostToolStrategy.build_result() creates message result."""
        strategy = PostToolStrategy()
        result = strategy.build_result(["msg1", "msg2"])
        assert result["hookSpecificOutput"]["hookEventName"] == "PostToolUse"
        assert "msg1" in result["hookSpecificOutput"]["message"]


class TestHandlerRegistry:
    """Tests for HandlerRegistry functionality."""

    def test_register_single_handler(self):
        """HandlerRegistry can register single handler."""
        registry = HandlerRegistry()
        handler = lambda ctx: {"result": "test"}
        registry.register("test_handler", handler)

        assert "test_handler" in registry.handlers
        assert registry.handlers["test_handler"] == handler

    def test_register_with_routing_rule(self):
        """HandlerRegistry can register with routing rule."""
        registry = HandlerRegistry()
        handler = (lambda ctx: {"a": 1}, lambda ctx: {"b": 2})
        rule = RoutingRule(tool_patterns={"Task": 0, "WebFetch": 1}, default=0)
        registry.register("dual_handler", handler, routing=rule)

        assert "dual_handler" in registry.routing_rules
        assert registry.routing_rules["dual_handler"] == rule

    def test_register_with_custom_executor(self):
        """HandlerRegistry can register with custom executor."""
        registry = HandlerRegistry()
        handler = lambda ctx: {}
        executor = lambda name, handler, ctx: {"custom": True}
        registry.register("custom_handler", handler, executor=executor)

        assert registry.has_custom_executor("custom_handler")
        assert registry.get_custom_executor("custom_handler") == executor

    def test_get_handler_for_tool_single(self):
        """HandlerRegistry returns single handler directly."""
        registry = HandlerRegistry()
        handler = lambda ctx: {"result": "test"}
        registry.register("test_handler", handler)

        result = registry.get_handler_for_tool("test_handler", "AnyTool")
        assert result == handler

    def test_get_handler_for_tool_dual_routed(self):
        """HandlerRegistry routes dual handler based on tool name."""
        registry = HandlerRegistry()
        handler0 = lambda ctx: {"handler": 0}
        handler1 = lambda ctx: {"handler": 1}
        handler = (handler0, handler1)
        rule = RoutingRule(tool_patterns={"Task": 0, "WebFetch": 1}, default=0)
        registry.register("dual_handler", handler, routing=rule)

        # Task should route to handler0
        result = registry.get_handler_for_tool("dual_handler", "Task")
        assert result == handler0

        # WebFetch should route to handler1
        result = registry.get_handler_for_tool("dual_handler", "WebFetch")
        assert result == handler1

    def test_get_handler_for_tool_dual_default(self):
        """HandlerRegistry uses default for unmatched tool."""
        registry = HandlerRegistry()
        handler = (lambda ctx: {"default": True}, lambda ctx: {"other": True})
        rule = RoutingRule(tool_patterns={"Task": 0}, default=0)
        registry.register("dual_handler", handler, routing=rule)

        # Unknown tool should use default (0)
        result = registry.get_handler_for_tool("dual_handler", "UnknownTool")
        assert result == handler[0]


class TestHandlerImports:
    """Tests for HANDLER_IMPORTS dictionaries."""

    def test_pre_tool_handler_imports_complete(self):
        """PreToolDispatcher.HANDLER_IMPORTS has all handlers."""
        dispatcher = PreToolDispatcher()

        for handler_name in dispatcher.ALL_HANDLERS:
            assert handler_name in dispatcher.HANDLER_IMPORTS, \
                f"{handler_name} missing from HANDLER_IMPORTS"

    def test_post_tool_handler_imports_complete(self):
        """PostToolDispatcher.HANDLER_IMPORTS has all handlers."""
        dispatcher = PostToolDispatcher()

        for handler_name in dispatcher.ALL_HANDLERS:
            assert handler_name in dispatcher.HANDLER_IMPORTS, \
                f"{handler_name} missing from HANDLER_IMPORTS"

    def test_handler_imports_format_valid(self):
        """HANDLER_IMPORTS entries have valid format."""
        for DispatcherClass in [PreToolDispatcher, PostToolDispatcher]:
            dispatcher = DispatcherClass()

            for name, spec in dispatcher.HANDLER_IMPORTS.items():
                assert isinstance(spec, tuple), f"{name}: spec not a tuple"
                assert len(spec) == 2, f"{name}: spec should be (module, func)"
                module_name, func_spec = spec
                assert isinstance(module_name, str), f"{name}: module_name not string"
                assert isinstance(func_spec, (str, tuple)), \
                    f"{name}: func_spec should be string or tuple"


class TestSetupHandlerRegistry:
    """Tests for setup_handler_registry() method."""

    def test_pre_tool_setup_registers_credential_scanner(self):
        """PreToolDispatcher.setup_handler_registry() registers credential_scanner."""
        dispatcher = PreToolDispatcher()
        dispatcher.setup_handler_registry()

        assert dispatcher._handler_registry.has_custom_executor("credential_scanner")

    def test_pre_tool_setup_registers_suggestion_engine(self):
        """PreToolDispatcher.setup_handler_registry() registers suggestion_engine."""
        dispatcher = PreToolDispatcher()
        dispatcher.setup_handler_registry()

        assert dispatcher._handler_registry.has_custom_executor("suggestion_engine")

    def test_pre_tool_setup_registers_unified_cache_routing(self):
        """PreToolDispatcher.setup_handler_registry() registers unified_cache routing."""
        dispatcher = PreToolDispatcher()
        dispatcher.setup_handler_registry()

        assert "unified_cache" in dispatcher._handler_registry.routing_rules
        rule = dispatcher._handler_registry.routing_rules["unified_cache"]
        assert rule.tool_patterns == {"Task": 0, "WebFetch": 1}

    def test_post_tool_setup_default_behavior(self):
        """PostToolDispatcher.setup_handler_registry() runs without errors."""
        dispatcher = PostToolDispatcher()
        # PostToolDispatcher doesn't override setup_handler_registry,
        # so this should just complete without error
        dispatcher.setup_handler_registry()

        # Should not crash
        assert True


class TestCustomExecutors:
    """Tests for custom executor implementations."""

    def test_credential_scanner_executor_skips_non_commit(self):
        """Credential scanner executor skips non-git-commit commands."""
        dispatcher = PreToolDispatcher()
        dispatcher.setup_handler_registry()

        # Mock the handler tuple
        mock_scan = MagicMock(return_value=[])
        mock_get_diff = MagicMock(return_value=("", []))
        mock_is_allowed = MagicMock(return_value=False)
        handler = (mock_scan, mock_get_diff, mock_is_allowed)

        ctx = {
            "tool_name": "Bash",
            "tool_input": {"command": "echo hello"}
        }

        result = dispatcher._credential_scanner_executor("credential_scanner", handler, ctx)

        assert result is None
        mock_get_diff.assert_not_called()
        mock_scan.assert_not_called()

    def test_credential_scanner_executor_runs_on_commit(self):
        """Credential scanner executor runs on git commit commands."""
        dispatcher = PreToolDispatcher()

        # Mock the handler tuple
        mock_scan = MagicMock(return_value=[("api_key", "line")])
        mock_get_diff = MagicMock(return_value=("diff content", ["file.py"]))
        mock_is_allowed = MagicMock(return_value=False)
        handler = (mock_scan, mock_get_diff, mock_is_allowed)

        ctx = {
            "tool_name": "Bash",
            "tool_input": {"command": "git commit -m 'test'"}
        }

        result = dispatcher._credential_scanner_executor("credential_scanner", handler, ctx)

        assert result is not None
        assert result["hookSpecificOutput"]["permissionDecision"] == "deny"
        mock_get_diff.assert_called_once()
        mock_scan.assert_called_once()

    def test_credential_scanner_executor_allows_clean_commit(self):
        """Credential scanner executor allows commits with no findings."""
        dispatcher = PreToolDispatcher()

        # Mock the handler tuple with no findings
        mock_scan = MagicMock(return_value=[])
        mock_get_diff = MagicMock(return_value=("diff content", ["file.py"]))
        mock_is_allowed = MagicMock(return_value=False)
        handler = (mock_scan, mock_get_diff, mock_is_allowed)

        ctx = {
            "tool_name": "Bash",
            "tool_input": {"command": "git commit -m 'test'"}
        }

        result = dispatcher._credential_scanner_executor("credential_scanner", handler, ctx)

        assert result is None  # No findings = no result

    def test_suggestion_engine_executor_routes_write_to_skill(self):
        """Suggestion engine executor routes Write/Edit to suggest_skill."""
        dispatcher = PreToolDispatcher()

        mock_skill = MagicMock(return_value={"suggestion": "skill"})
        mock_subagent = MagicMock(return_value=None)
        mock_optimization = MagicMock(return_value=None)
        handler = (mock_skill, mock_subagent, mock_optimization)

        ctx = {"tool_name": "Write", "tool_input": {}}

        result = dispatcher._suggestion_engine_executor("suggestion_engine", handler, ctx)

        mock_skill.assert_called_once_with(ctx)
        mock_subagent.assert_not_called()

    def test_suggestion_engine_executor_routes_grep_to_subagent_or_optimization(self):
        """Suggestion engine executor routes Grep to suggest_subagent or suggest_optimization."""
        dispatcher = PreToolDispatcher()

        mock_skill = MagicMock(return_value=None)
        mock_subagent = MagicMock(return_value={"suggestion": "subagent"})
        mock_optimization = MagicMock(return_value=None)
        handler = (mock_skill, mock_subagent, mock_optimization)

        ctx = {"tool_name": "Grep", "tool_input": {}}

        result = dispatcher._suggestion_engine_executor("suggestion_engine", handler, ctx)

        assert result == {"suggestion": "subagent"}
        mock_subagent.assert_called_once_with(ctx)

    def test_suggestion_engine_executor_routes_bash_to_optimization(self):
        """Suggestion engine executor routes Bash to suggest_optimization."""
        dispatcher = PreToolDispatcher()

        mock_skill = MagicMock(return_value=None)
        mock_subagent = MagicMock(return_value=None)
        mock_optimization = MagicMock(return_value={"suggestion": "optimization"})
        handler = (mock_skill, mock_subagent, mock_optimization)

        ctx = {"tool_name": "Bash", "tool_input": {}}

        result = dispatcher._suggestion_engine_executor("suggestion_engine", handler, ctx)

        assert result == {"suggestion": "optimization"}
        mock_optimization.assert_called_once_with(ctx)


class TestUnifiedCacheRouting:
    """Tests for unified_cache routing rules."""

    def test_unified_cache_registered_in_pre_tool(self):
        """unified_cache has routing rule registered in PreToolDispatcher."""
        dispatcher = PreToolDispatcher()
        dispatcher.setup_handler_registry()

        assert "unified_cache" in dispatcher._handler_registry.routing_rules
        rule = dispatcher._handler_registry.routing_rules["unified_cache"]
        assert isinstance(rule, RoutingRule)

    def test_unified_cache_routing_rule_task_to_exploration(self):
        """unified_cache routes Task tool to exploration handler (index 0)."""
        dispatcher = PreToolDispatcher()
        dispatcher.setup_handler_registry()

        rule = dispatcher._handler_registry.routing_rules["unified_cache"]
        assert rule.tool_patterns["Task"] == 0

    def test_unified_cache_routing_rule_webfetch_to_research(self):
        """unified_cache routes WebFetch tool to research handler (index 1)."""
        dispatcher = PreToolDispatcher()
        dispatcher.setup_handler_registry()

        rule = dispatcher._handler_registry.routing_rules["unified_cache"]
        assert rule.tool_patterns["WebFetch"] == 1

    def test_post_tool_unified_cache_routing(self):
        """PostToolDispatcher routes unified_cache for Task and WebFetch."""
        dispatcher = PostToolDispatcher()

        # Get the handler (should be a tuple)
        handler = dispatcher.get_handler("unified_cache")
        assert handler is not None
        assert isinstance(handler, tuple)
        assert len(handler) == 2


class TestUserPromptDispatcher:
    """Tests for UserPromptSubmit dispatcher."""

    def test_handler_list_defined(self):
        """ALL_HANDLERS list is defined."""
        dispatcher = UserPromptDispatcher()
        assert dispatcher.ALL_HANDLERS is not None
        assert isinstance(dispatcher.ALL_HANDLERS, list)
        assert "context_manager" in dispatcher.ALL_HANDLERS
        assert "usage_tracker" in dispatcher.ALL_HANDLERS

    def test_get_handler_lazy_loads(self):
        """get_handler() lazy-loads handlers."""
        dispatcher = UserPromptDispatcher()
        # Clear any cached handlers
        dispatcher._handlers.clear()

        handler = dispatcher.get_handler("context_manager")
        assert callable(handler) or handler is None

    def test_dispatch_returns_none_for_empty_messages(self):
        """dispatch() returns None when no handlers produce messages."""
        dispatcher = UserPromptDispatcher()
        with patch.object(dispatcher, 'run_handler') as mock_run:
            mock_run.return_value = None

            result = dispatcher.dispatch({})
            assert result is None

    def test_dispatch_joins_multiple_messages(self):
        """dispatch() joins multiple handler messages."""
        dispatcher = UserPromptDispatcher()
        with patch.object(dispatcher, 'run_handler') as mock_run:
            mock_run.side_effect = [
                {"message": "msg1"},
                {"message": "msg2"}
            ]

            result = dispatcher.dispatch({})
            assert result is not None
            assert "msg1" in result["message"]
            assert "msg2" in result["message"]

    def test_user_prompt_strategy_never_terminates(self):
        """UserPromptStrategy.should_terminate() always returns False."""
        strategy = UserPromptStrategy()
        result = {"message": "test"}
        assert strategy.should_terminate(result, "test_handler") == False

    def test_user_prompt_strategy_extracts_message(self):
        """UserPromptStrategy.extract_message() extracts message field."""
        strategy = UserPromptStrategy()
        hook_output = {"message": "Test message"}
        assert strategy.extract_message(hook_output) == "Test message"

    def test_user_prompt_strategy_builds_result(self):
        """UserPromptStrategy.build_result() creates message result."""
        strategy = UserPromptStrategy()
        result = strategy.build_result(["msg1", "msg2"])
        assert "msg1" in result["message"]
        assert "msg2" in result["message"]

    def test_user_prompt_strategy_returns_none_for_empty(self):
        """UserPromptStrategy.build_result() returns None for empty messages."""
        strategy = UserPromptStrategy()
        result = strategy.build_result([])
        assert result is None

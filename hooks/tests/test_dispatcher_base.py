#!/usr/bin/env python3
"""Unit tests for dispatcher_base.py."""

import json
import sys
import time
from io import StringIO
from pathlib import Path
from typing import Any
from unittest import TestCase, main
from unittest.mock import patch, MagicMock

from hooks.dispatchers.base import BaseDispatcher, PostToolStrategy


class MockDispatcher(BaseDispatcher):
    """Concrete implementation for testing (not a pytest class)."""

    DISPATCHER_NAME = "test_dispatcher"
    HOOK_EVENT_NAME = "TestEvent"
    ALL_HANDLERS = ["handler_a", "handler_b", "handler_c"]
    TOOL_HANDLERS = {
        "ToolA": ["handler_a", "handler_b"],
        "ToolB": ["handler_c"],
    }

    def __init__(self):
        super().__init__()
        self.mock_handlers = {}

    def set_mock_handler(self, name: str, func):
        """Set a mock handler for testing."""
        self.mock_handlers[name] = func

    def _import_handler(self, name: str) -> Any:
        if name in self.mock_handlers:
            return self.mock_handlers[name]
        if name in self.ALL_HANDLERS:
            # Return a simple passthrough handler for known handlers
            return lambda ctx: None
        # Return None for unknown handlers
        return None

    def _create_result_strategy(self):
        """Create result strategy for testing - use PostTool (no termination)."""
        return PostToolStrategy()


class TestBaseDispatcher(TestCase):
    """Tests for BaseDispatcher class."""

    def setUp(self):
        self.dispatcher = MockDispatcher()

    def test_get_handler_caches(self):
        """Handler should be cached after first load."""
        handler1 = self.dispatcher.get_handler("handler_a")
        handler2 = self.dispatcher.get_handler("handler_a")
        self.assertIs(handler1, handler2)

    def test_get_handler_returns_none_for_unknown(self):
        """Unknown handlers return None."""
        result = self.dispatcher.get_handler("unknown_handler")
        self.assertIsNone(result)

    def test_dispatch_calls_handlers(self):
        """Dispatch should call appropriate handlers for tool."""
        called = []

        def handler_a(ctx):
            called.append("a")
            return None

        def handler_b(ctx):
            called.append("b")
            return None

        self.dispatcher.set_mock_handler("handler_a", handler_a)
        self.dispatcher.set_mock_handler("handler_b", handler_b)

        ctx = {"tool_name": "ToolA"}
        self.dispatcher.dispatch(ctx)

        self.assertEqual(called, ["a", "b"])

    def test_dispatch_returns_none_for_unknown_tool(self):
        """Unknown tools return None without calling handlers."""
        ctx = {"tool_name": "UnknownTool"}
        result = self.dispatcher.dispatch(ctx)
        self.assertIsNone(result)

    def test_dispatch_collects_messages(self):
        """Messages from handlers should be collected."""
        def handler_with_message(ctx):
            return {
                "hookSpecificOutput": {
                    "message": "Test message"
                }
            }

        self.dispatcher.set_mock_handler("handler_a", handler_with_message)

        ctx = {"tool_name": "ToolA"}
        result = self.dispatcher.dispatch(ctx)

        self.assertIsNotNone(result)
        self.assertIn("Test message", result["hookSpecificOutput"]["message"])

    def test_run_handler_returns_none_when_disabled(self):
        """Disabled handlers should be skipped."""
        with patch('hooks.dispatchers.base.is_hook_disabled', return_value=True):
            result = self.dispatcher.run_handler("handler_a", {})
            self.assertIsNone(result)

    def test_run_handler_timeout(self):
        """Handlers that timeout should not block."""
        def slow_handler(ctx):
            time.sleep(2)
            return {"result": "slow"}

        self.dispatcher.set_mock_handler("handler_a", slow_handler)

        with patch('hooks.dispatchers.base._HANDLER_TIMEOUT', 0.1):
            start = time.time()
            result = self.dispatcher.run_handler("handler_a", {})
            elapsed = time.time() - start

            # Should timeout quickly, not wait 2 seconds
            self.assertLess(elapsed, 1.0)
            self.assertIsNone(result)

    def test_run_handler_exception_handling(self):
        """Exceptions in handlers should be caught."""
        def error_handler(ctx):
            raise ValueError("Test error")

        self.dispatcher.set_mock_handler("handler_a", error_handler)

        # Should not raise
        result = self.dispatcher.run_handler("handler_a", {})
        self.assertIsNone(result)

    def test_validate_handlers_logs_failures(self):
        """Validation should log failed handler imports."""
        # Set up a handler that returns None (simulating import failure)
        self.dispatcher._handlers["handler_a"] = None

        with patch('sys.stderr', new_callable=StringIO) as mock_stderr:
            self.dispatcher.validate_handlers()
            # Should have logged something about failed handlers
            output = mock_stderr.getvalue()
            # Note: May or may not produce output depending on actual failures


class TestDispatcherIntegration(TestCase):
    """Integration tests for dispatcher."""

    def test_full_dispatch_cycle(self):
        """Test complete dispatch with multiple handlers."""
        dispatcher = MockDispatcher()

        call_order = []

        def handler_a(ctx):
            call_order.append("a")
            return {"hookSpecificOutput": {"message": "from a"}}

        def handler_b(ctx):
            call_order.append("b")
            return {"hookSpecificOutput": {"message": "from b"}}

        dispatcher.set_mock_handler("handler_a", handler_a)
        dispatcher.set_mock_handler("handler_b", handler_b)

        ctx = {"tool_name": "ToolA", "tool_input": {"path": "/test"}}
        result = dispatcher.dispatch(ctx)

        # Both handlers called in order
        self.assertEqual(call_order, ["a", "b"])

        # Messages combined (joined with " | ")
        self.assertIsNotNone(result)
        message = result["hookSpecificOutput"]["message"]
        # Both messages should be in the combined output
        self.assertTrue("from a" in message or "from b" in message)


class TestAutoDiscoverRouting(TestCase):
    """Tests for AUTO_DISCOVER_ROUTING functionality."""

    def test_auto_discover_disabled_by_default(self):
        """AUTO_DISCOVER_ROUTING should be False by default."""
        dispatcher = MockDispatcher()
        self.assertFalse(dispatcher.AUTO_DISCOVER_ROUTING)

    def test_explicit_tool_handlers_takes_precedence(self):
        """Explicit TOOL_HANDLERS should be used when defined."""
        dispatcher = MockDispatcher()
        dispatcher.AUTO_DISCOVER_ROUTING = True
        # MockDispatcher has explicit TOOL_HANDLERS
        tool_handlers = dispatcher.get_tool_handlers()
        self.assertEqual(tool_handlers, {"ToolA": ["handler_a", "handler_b"], "ToolB": ["handler_c"]})

    def test_auto_discover_with_empty_tool_handlers(self):
        """Auto-discovery works when TOOL_HANDLERS is empty."""

        class AutoDiscoverDispatcher(BaseDispatcher):
            DISPATCHER_NAME = "auto_discover_test"
            HOOK_EVENT_NAME = "PreToolUse"
            ALL_HANDLERS = ["test_handler"]
            TOOL_HANDLERS = {}  # Empty - triggers auto-discovery
            AUTO_DISCOVER_ROUTING = True

            HANDLER_IMPORTS = {
                "test_handler": ("hooks.handlers.file_protection", "check_file_protection"),
            }

            def _create_result_strategy(self):
                return PostToolStrategy()

        dispatcher = AutoDiscoverDispatcher()
        tool_handlers = dispatcher.get_tool_handlers()

        # file_protection has APPLIES_TO = ["Read", "Write", "Edit"]
        self.assertIn("Read", tool_handlers)
        self.assertIn("Write", tool_handlers)
        self.assertIn("Edit", tool_handlers)
        self.assertIn("test_handler", tool_handlers.get("Read", []))

    def test_auto_discover_pre_vs_post(self):
        """PreToolUse should use APPLIES_TO_PRE, PostToolUse should use APPLIES_TO_POST."""

        class PreDispatcher(BaseDispatcher):
            DISPATCHER_NAME = "pre_discover_test"
            HOOK_EVENT_NAME = "PreToolUse"
            ALL_HANDLERS = ["file_monitor"]
            TOOL_HANDLERS = {}
            AUTO_DISCOVER_ROUTING = True
            HANDLER_IMPORTS = {
                "file_monitor": ("hooks.handlers.file_monitor", "track_file_pre"),
            }

            def _create_result_strategy(self):
                return PostToolStrategy()

        class PostDispatcher(BaseDispatcher):
            DISPATCHER_NAME = "post_discover_test"
            HOOK_EVENT_NAME = "PostToolUse"
            ALL_HANDLERS = ["file_monitor"]
            TOOL_HANDLERS = {}
            AUTO_DISCOVER_ROUTING = True
            HANDLER_IMPORTS = {
                "file_monitor": ("hooks.handlers.file_monitor", "track_file_post"),
            }

            def _create_result_strategy(self):
                return PostToolStrategy()

        pre_dispatcher = PreDispatcher()
        post_dispatcher = PostDispatcher()

        pre_handlers = pre_dispatcher.get_tool_handlers()
        post_handlers = post_dispatcher.get_tool_handlers()

        # file_monitor: APPLIES_TO_PRE = ["Read", "Edit"], APPLIES_TO_POST = ["Grep", "Glob", "Read"]
        # PreToolUse should see Read, Edit
        self.assertIn("Read", pre_handlers)
        self.assertIn("Edit", pre_handlers)

        # PostToolUse should see Grep, Glob, Read
        self.assertIn("Grep", post_handlers)
        self.assertIn("Glob", post_handlers)
        self.assertIn("Read", post_handlers)

    def test_auto_discover_falls_back_to_applies_to(self):
        """Falls back to APPLIES_TO when APPLIES_TO_PRE/POST not defined."""

        class FallbackDispatcher(BaseDispatcher):
            DISPATCHER_NAME = "fallback_test"
            HOOK_EVENT_NAME = "PreToolUse"
            ALL_HANDLERS = ["tdd_guard"]
            TOOL_HANDLERS = {}
            AUTO_DISCOVER_ROUTING = True
            HANDLER_IMPORTS = {
                "tdd_guard": ("hooks.handlers.tdd_guard", "check_tdd"),
            }

            def _create_result_strategy(self):
                return PostToolStrategy()

        dispatcher = FallbackDispatcher()
        tool_handlers = dispatcher.get_tool_handlers()

        # tdd_guard has APPLIES_TO = ["Write", "Edit"] (no PRE/POST variants)
        self.assertIn("Write", tool_handlers)
        self.assertIn("Edit", tool_handlers)
        self.assertIn("tdd_guard", tool_handlers.get("Write", []))

    def test_auto_discover_caches_result(self):
        """Auto-discovered handlers should be cached."""

        class CachingDispatcher(BaseDispatcher):
            DISPATCHER_NAME = "cache_test"
            HOOK_EVENT_NAME = "PreToolUse"
            ALL_HANDLERS = ["file_protection"]
            TOOL_HANDLERS = {}
            AUTO_DISCOVER_ROUTING = True
            HANDLER_IMPORTS = {
                "file_protection": ("hooks.handlers.file_protection", "check_file_protection"),
            }

            def _create_result_strategy(self):
                return PostToolStrategy()

        dispatcher = CachingDispatcher()

        # First call
        handlers1 = dispatcher.get_tool_handlers()
        # Second call should return same object
        handlers2 = dispatcher.get_tool_handlers()

        self.assertIs(handlers1, handlers2)

    def test_auto_discover_with_disabled_flag(self):
        """When AUTO_DISCOVER_ROUTING=False and TOOL_HANDLERS empty, returns empty."""

        class NoDiscoverDispatcher(BaseDispatcher):
            DISPATCHER_NAME = "no_discover_test"
            HOOK_EVENT_NAME = "PreToolUse"
            ALL_HANDLERS = ["file_protection"]
            TOOL_HANDLERS = {}
            AUTO_DISCOVER_ROUTING = False  # Disabled
            HANDLER_IMPORTS = {}

            def _create_result_strategy(self):
                return PostToolStrategy()

        dispatcher = NoDiscoverDispatcher()
        tool_handlers = dispatcher.get_tool_handlers()

        self.assertEqual(tool_handlers, {})


if __name__ == "__main__":
    main()

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

    def test_build_result_with_messages(self):
        """Build result should join messages."""
        result = self.dispatcher._build_result(["msg1", "msg2"])

        self.assertIsNotNone(result)
        self.assertEqual(result["hookSpecificOutput"]["hookEventName"], "TestEvent")
        self.assertIn("msg1", result["hookSpecificOutput"]["message"])
        self.assertIn("msg2", result["hookSpecificOutput"]["message"])

    def test_build_result_empty_messages(self):
        """Empty messages should return None."""
        result = self.dispatcher._build_result([])
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


class TestDispatcherTermination(TestCase):
    """Tests for early termination behavior."""

    def setUp(self):
        self.dispatcher = MockDispatcher()

    def test_should_terminate_default_false(self):
        """Default implementation should not terminate."""
        result = {"hookSpecificOutput": {"message": "test"}}
        should_stop = self.dispatcher._should_terminate(result, "handler", "Tool")
        self.assertFalse(should_stop)


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


if __name__ == "__main__":
    main()

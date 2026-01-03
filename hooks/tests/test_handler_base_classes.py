#!/home/jonglaser/.claude/data/venv/bin/python3
"""
Tests for HookHandler and StatefulHandler base classes.

Tests P5.11 (HookHandler) and P5.12 (StatefulHandler) implementations.
"""
import time
from unittest import TestCase
from unittest.mock import patch, MagicMock

from hooks.hook_sdk import (
    HookHandler,
    StatefulHandler,
    PreToolUseContext,
    PostToolUseContext,
    BaseContext,
    Response,
)


# =============================================================================
# HookHandler Tests (P5.11)
# =============================================================================

class TestHookHandler(TestCase):
    """Tests for HookHandler base class."""

    def test_default_applies_returns_true(self):
        """Default applies() returns True when no tools filter."""
        handler = HookHandler()
        ctx = PreToolUseContext({"tool_name": "Read"})
        self.assertTrue(handler.applies(ctx))

    def test_applies_filters_by_tool(self):
        """applies() filters by tool name when tools is set."""
        class FilteredHandler(HookHandler):
            tools = ["Read", "Edit"]

        handler = FilteredHandler()

        # Matching tool
        ctx = PreToolUseContext({"tool_name": "Read"})
        self.assertTrue(handler.applies(ctx))

        # Non-matching tool
        ctx = PreToolUseContext({"tool_name": "Bash"})
        self.assertFalse(handler.applies(ctx))

    def test_applies_with_empty_tools_list(self):
        """applies() with empty tools list filters all tools."""
        class EmptyToolsHandler(HookHandler):
            tools = []

        handler = EmptyToolsHandler()
        ctx = PreToolUseContext({"tool_name": "Read"})
        self.assertFalse(handler.applies(ctx))

    def test_handle_raises_not_implemented(self):
        """handle() raises NotImplementedError in base class."""
        handler = HookHandler()
        ctx = PreToolUseContext({"tool_name": "Read"})

        with self.assertRaises(NotImplementedError):
            handler.handle(ctx)

    def test_create_context_pre_tool_use(self):
        """_create_context creates PreToolUseContext for PreToolUse event."""
        handler = HookHandler()
        handler.event = "PreToolUse"

        raw = {"tool_name": "Read", "tool_input": {"file_path": "/test"}}
        ctx = handler._create_context(raw)

        self.assertIsInstance(ctx, PreToolUseContext)
        self.assertEqual(ctx.tool_name, "Read")

    def test_create_context_post_tool_use(self):
        """_create_context creates PostToolUseContext for PostToolUse event."""
        handler = HookHandler()
        handler.event = "PostToolUse"

        raw = {"tool_name": "Read", "tool_response": {"content": "test"}}
        ctx = handler._create_context(raw)

        self.assertIsInstance(ctx, PostToolUseContext)

    def test_create_context_other_event(self):
        """_create_context creates BaseContext for other events."""
        handler = HookHandler()
        handler.event = "SessionStart"

        raw = {"cwd": "/home/test"}
        ctx = handler._create_context(raw)

        self.assertIsInstance(ctx, BaseContext)

    def test_call_invokes_handle_when_applies(self):
        """__call__ invokes handle() when applies() returns True."""
        class TestHandler(HookHandler):
            name = "test_handler"

            def handle(self, ctx):
                return self.message("handled")

        handler = TestHandler()
        raw = {"tool_name": "Read"}
        result = handler(raw)

        self.assertIsNotNone(result)
        self.assertIn("message", result["hookSpecificOutput"])

    def test_call_skips_when_applies_false(self):
        """__call__ returns None when applies() returns False."""
        class FilteredHandler(HookHandler):
            name = "filtered_handler"
            tools = ["Bash"]

            def handle(self, ctx):
                return self.message("should not reach")

        handler = FilteredHandler()
        raw = {"tool_name": "Read"}
        result = handler(raw)

        self.assertIsNone(result)

    def test_call_catches_exceptions(self):
        """__call__ catches exceptions and returns None."""
        class ErrorHandler(HookHandler):
            name = "error_handler"

            def handle(self, ctx):
                raise ValueError("Test error")

        handler = ErrorHandler()
        raw = {"tool_name": "Read"}

        with patch("hooks.hook_sdk.log_event"):
            result = handler(raw)

        self.assertIsNone(result)

    def test_allow_method(self):
        """allow() returns proper response structure."""
        handler = HookHandler()
        result = handler.allow("Test reason")

        self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "allow")
        self.assertEqual(result["hookSpecificOutput"]["permissionDecisionReason"], "Test reason")

    def test_deny_method(self):
        """deny() returns proper response structure."""
        handler = HookHandler()
        result = handler.deny("Blocked")

        self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertEqual(result["hookSpecificOutput"]["permissionDecisionReason"], "Blocked")

    def test_message_method_uses_handler_event(self):
        """message() uses handler's event type."""
        class PostHandler(HookHandler):
            event = "PostToolUse"

        handler = PostHandler()
        result = handler.message("Test message")

        self.assertEqual(result["hookSpecificOutput"]["hookEventName"], "PostToolUse")
        self.assertEqual(result["hookSpecificOutput"]["message"], "Test message")

    def test_custom_applies_override(self):
        """Custom applies() override is respected."""
        class CustomAppliesHandler(HookHandler):
            name = "custom_applies"

            def applies(self, ctx):
                # Only apply if file_path contains "important"
                file_path = ctx.tool_input.file_path
                return "important" in file_path

            def handle(self, ctx):
                return self.message("handled")

        handler = CustomAppliesHandler()

        # Should apply
        raw = {"tool_name": "Read", "tool_input": {"file_path": "/important/file.txt"}}
        result = handler(raw)
        self.assertIsNotNone(result)

        # Should not apply
        raw = {"tool_name": "Read", "tool_input": {"file_path": "/other/file.txt"}}
        result = handler(raw)
        self.assertIsNone(result)


class TestHookHandlerIntegration(TestCase):
    """Integration tests for HookHandler with real implementations."""

    def test_blocking_pattern(self):
        """Test blocking pattern using HookHandler."""
        class CommandBlocker(HookHandler):
            name = "command_blocker"
            tools = ["Bash"]
            event = "PreToolUse"

            def handle(self, ctx):
                command = ctx.tool_input.command
                if "rm -rf" in command:
                    return self.deny("Dangerous command blocked")
                return None

        handler = CommandBlocker()

        # Should block
        raw = {"tool_name": "Bash", "tool_input": {"command": "rm -rf /"}}
        result = handler(raw)
        self.assertIsNotNone(result)
        self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "deny")

        # Should allow
        raw = {"tool_name": "Bash", "tool_input": {"command": "ls -la"}}
        result = handler(raw)
        self.assertIsNone(result)

        # Should skip (wrong tool)
        raw = {"tool_name": "Read", "tool_input": {"file_path": "/test"}}
        result = handler(raw)
        self.assertIsNone(result)


# =============================================================================
# StatefulHandler Tests (P5.12)
# =============================================================================

class TestStatefulHandler(TestCase):
    """Tests for StatefulHandler base class."""

    def setUp(self):
        """Set up test fixtures."""
        self.session_id = "test-session-stateful"

    def test_process_raises_not_implemented(self):
        """process() raises NotImplementedError in base class."""
        handler = StatefulHandler()

        with self.assertRaises(NotImplementedError):
            handler.process(None, {})

    def test_get_default_state_returns_empty_dict(self):
        """_get_default_state returns empty dict when default_state is None."""
        handler = StatefulHandler()
        self.assertEqual(handler._get_default_state(), {})

    def test_get_default_state_returns_copy(self):
        """_get_default_state returns copy of default_state."""
        class HandlerWithDefault(StatefulHandler):
            default_state = {"count": 0, "items": []}

        handler = HandlerWithDefault()
        state1 = handler._get_default_state()
        state2 = handler._get_default_state()

        # Should be equal but not same object
        self.assertEqual(state1, state2)
        self.assertIsNot(state1, state2)

        # Modifying one shouldn't affect the other
        state1["count"] = 5
        self.assertEqual(state2["count"], 0)

    @patch("hooks.hook_sdk.HookState")
    def test_load_state_calls_hook_state(self, mock_hook_state_class):
        """load_state calls underlying HookState.load()."""
        mock_hook_state = MagicMock()
        mock_hook_state.load.return_value = {"count": 5}
        mock_hook_state_class.return_value = mock_hook_state

        class TestHandler(StatefulHandler):
            namespace = "test_ns"
            default_state = {"count": 0}

        handler = TestHandler()
        result = handler.load_state("session-123")

        mock_hook_state.load.assert_called_once()
        self.assertEqual(result, {"count": 5})

    @patch("hooks.hook_sdk.HookState")
    def test_save_state_without_pruning(self, mock_hook_state_class):
        """save_state calls save() when no pruning config."""
        mock_hook_state = MagicMock()
        mock_hook_state_class.return_value = mock_hook_state

        class TestHandler(StatefulHandler):
            namespace = "test_ns"
            # No max_entries or items_key

        handler = TestHandler()
        handler.save_state("session-123", {"count": 5})

        mock_hook_state.save.assert_called_once()
        mock_hook_state.save_with_pruning.assert_not_called()

    @patch("hooks.hook_sdk.HookState")
    def test_save_state_with_pruning(self, mock_hook_state_class):
        """save_state calls save_with_pruning() when pruning config set."""
        mock_hook_state = MagicMock()
        mock_hook_state_class.return_value = mock_hook_state

        class TestHandler(StatefulHandler):
            namespace = "test_ns"
            max_entries = 100
            items_key = "items"
            time_key = "ts"

        handler = TestHandler()
        handler.save_state("session-123", {"items": {}})

        mock_hook_state.save_with_pruning.assert_called_once_with(
            {"items": {}},
            session_id="session-123",
            max_entries=100,
            items_key="items",
            time_key="ts"
        )

    def test_handle_loads_and_saves_state(self):
        """handle() loads state, calls process(), saves state."""
        class TestHandler(StatefulHandler):
            namespace = "test_handle"
            default_state = {"count": 0}

            def process(self, ctx, state):
                state["count"] += 1
                return None

        handler = TestHandler()

        # Mock the state methods
        handler.load_state = MagicMock(return_value={"count": 0})
        handler.save_state = MagicMock()

        ctx = MagicMock()
        ctx.session_id = "session-123"

        handler.handle(ctx)

        handler.load_state.assert_called_once_with("session-123")
        handler.save_state.assert_called_once()
        # State should have been modified
        saved_state = handler.save_state.call_args[0][1]
        self.assertEqual(saved_state["count"], 1)

    def test_handle_returns_process_result(self):
        """handle() returns whatever process() returns."""
        class TestHandler(StatefulHandler):
            namespace = "test_return"
            default_state = {}

            def process(self, ctx, state):
                return self.message("Result from process")

        handler = TestHandler()
        handler.load_state = MagicMock(return_value={})
        handler.save_state = MagicMock()

        ctx = MagicMock()
        ctx.session_id = "session-123"

        result = handler.handle(ctx)

        self.assertIsNotNone(result)
        self.assertIn("message", result["hookSpecificOutput"])

    def test_inherits_from_hook_handler(self):
        """StatefulHandler inherits from HookHandler."""
        handler = StatefulHandler()
        self.assertIsInstance(handler, HookHandler)

    def test_applies_from_parent(self):
        """applies() from HookHandler works in StatefulHandler."""
        class FilteredStatefulHandler(StatefulHandler):
            tools = ["Edit"]

        handler = FilteredStatefulHandler()

        ctx = PreToolUseContext({"tool_name": "Edit"})
        self.assertTrue(handler.applies(ctx))

        ctx = PreToolUseContext({"tool_name": "Read"})
        self.assertFalse(handler.applies(ctx))


class TestStatefulHandlerIntegration(TestCase):
    """Integration tests for StatefulHandler with mocked state storage."""

    def test_counter_handler_pattern(self):
        """Test common counter pattern with StatefulHandler."""
        class CounterHandler(StatefulHandler):
            name = "counter_handler"
            namespace = "counter"
            tools = ["Read"]
            event = "PostToolUse"
            default_state = {"count": 0}

            def process(self, ctx, state):
                state["count"] += 1
                if state["count"] >= 3:
                    return self.message(f"Read {state['count']} files")
                return None

        handler = CounterHandler()

        # Mock state storage
        stored_state = {"count": 0}

        def mock_load(session_id):
            return stored_state.copy()

        def mock_save(session_id, state):
            stored_state.update(state)

        handler.load_state = mock_load
        handler.save_state = mock_save

        # First two reads - no message
        for _ in range(2):
            raw = {"tool_name": "Read", "tool_input": {"file_path": "/test"}}
            result = handler(raw)
            self.assertIsNone(result)

        # Third read - should show message
        raw = {"tool_name": "Read", "tool_input": {"file_path": "/test"}}
        result = handler(raw)
        self.assertIsNotNone(result)
        self.assertIn("3 files", result["hookSpecificOutput"]["message"])

    def test_tracking_handler_pattern(self):
        """Test file tracking pattern with StatefulHandler."""
        class FileTracker(StatefulHandler):
            name = "file_tracker"
            namespace = "file_tracker"
            tools = ["Read"]
            event = "PreToolUse"
            default_state = {"files": {}}
            max_entries = 10
            items_key = "files"
            time_key = "ts"

            def process(self, ctx, state):
                file_path = ctx.tool_input.file_path
                if file_path in state["files"]:
                    return self.message(f"Already read: {file_path}")
                state["files"][file_path] = {"ts": time.time()}
                return None

        handler = FileTracker()

        # Mock state storage
        stored_state = {"files": {}}

        def mock_load(session_id):
            return stored_state.copy()

        def mock_save(session_id, state):
            stored_state.update(state)

        handler.load_state = mock_load
        handler.save_state = mock_save

        # First read of file - no warning
        raw = {"tool_name": "Read", "tool_input": {"file_path": "/test/file.txt"}}
        result = handler(raw)
        self.assertIsNone(result)

        # Second read of same file - warning
        result = handler(raw)
        self.assertIsNotNone(result)
        self.assertIn("Already read", result["hookSpecificOutput"]["message"])

        # Different file - no warning
        raw = {"tool_name": "Read", "tool_input": {"file_path": "/test/other.txt"}}
        result = handler(raw)
        self.assertIsNone(result)


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================

class TestEdgeCases(TestCase):
    """Test edge cases for both base classes."""

    def test_handler_with_missing_tool_name(self):
        """Handler handles missing tool_name gracefully.

        When tool_name is missing/empty, the filter passes through
        (empty string is falsy, skipping the 'not in tools' check).
        This lets the handler decide how to handle missing tool_name.
        """
        class SafeHandler(HookHandler):
            tools = ["Read"]

            def handle(self, ctx):
                # Handler should check for empty tool_name if needed
                if not ctx.tool_name:
                    return None
                return self.message("handled")

        handler = SafeHandler()
        raw = {}  # No tool_name
        result = handler(raw)

        # Handler's own check should return None for missing tool_name
        self.assertIsNone(result)

    def test_stateful_handler_with_corrupted_state(self):
        """StatefulHandler handles corrupted state gracefully."""
        class RobustHandler(StatefulHandler):
            namespace = "robust"
            default_state = {"count": 0}

            def process(self, ctx, state):
                # Even if state is corrupted, this should work
                count = state.get("count", 0)
                state["count"] = count + 1
                return None

        handler = RobustHandler()

        # Mock load to return corrupted state (missing expected key)
        handler.load_state = MagicMock(return_value={"wrong_key": "value"})
        handler.save_state = MagicMock()

        ctx = MagicMock()
        ctx.session_id = "session-123"

        # Should not crash
        result = handler.handle(ctx)
        self.assertIsNone(result)

    def test_handler_with_none_tools(self):
        """Handler with tools=None accepts all tools."""
        class AcceptAllHandler(HookHandler):
            tools = None  # Explicit None

            def handle(self, ctx):
                return self.message("handled")

        handler = AcceptAllHandler()

        for tool in ["Read", "Write", "Edit", "Bash", "Grep", "Custom"]:
            raw = {"tool_name": tool}
            ctx = handler._create_context(raw)
            self.assertTrue(handler.applies(ctx))

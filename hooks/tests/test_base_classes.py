"""Tests for hook_utils/base.py base classes."""

import pytest
from unittest.mock import patch, MagicMock

from hooks.hook_utils.base import (
    BlockingHook,
    MonitoringHook,
    SuggestionHook,
    StateTrackingHook,
)


class TestBlockingHook:
    """Tests for BlockingHook base class."""

    def test_deny_returns_proper_structure(self):
        """deny() should return PreToolUse deny response."""
        class TestBlocker(BlockingHook):
            def check(self, ctx):
                return self.deny("Test reason")

        blocker = TestBlocker("test_blocker")
        result = blocker.deny("blocked for testing")

        assert result == {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": "blocked for testing"
            }
        }

    def test_check_returns_none_allows(self):
        """Returning None from check() allows the operation."""
        class AllowAll(BlockingHook):
            def check(self, ctx):
                return None

        blocker = AllowAll("allow_all")
        assert blocker.check({}) is None

    def test_callable_interface(self):
        """BlockingHook should be callable."""
        class CountingBlocker(BlockingHook):
            def __init__(self):
                super().__init__("counter")
                self.call_count = 0

            def check(self, ctx):
                self.call_count += 1
                return None

        blocker = CountingBlocker()
        blocker({"tool_name": "Test"})
        blocker({"tool_name": "Test"})

        assert blocker.call_count == 2

    def test_name_attribute(self):
        """Hook should store its name."""
        class NamedHook(BlockingHook):
            def check(self, ctx):
                return None

        hook = NamedHook("my_hook_name")
        assert hook.name == "my_hook_name"


class TestMonitoringHook:
    """Tests for MonitoringHook base class."""

    def test_process_updates_state(self):
        """process() should update state dict."""
        class Counter(MonitoringHook):
            def process(self, ctx, state):
                state['count'] = state.get('count', 0) + 1
                return state, None

        counter = Counter("counter")
        state = {}
        new_state, response = counter.process({}, state)

        assert new_state['count'] == 1
        assert response is None

    def test_process_can_return_response(self):
        """process() can return a response to Claude."""
        class Responder(MonitoringHook):
            def process(self, ctx, state):
                return state, {"message": "hello"}

        responder = Responder("responder")
        _, response = responder.process({}, {})

        assert response == {"message": "hello"}

    @patch('hooks.hook_utils.base.read_state')
    @patch('hooks.hook_utils.base.write_state')
    def test_load_save_state_global(self, mock_write, mock_read):
        """Global state uses read_state/write_state."""
        mock_read.return_value = {"existing": True}

        class GlobalMonitor(MonitoringHook):
            def process(self, ctx, state):
                return state, None

        monitor = GlobalMonitor("global_monitor", use_session=False)
        state = monitor.load_state()

        mock_read.assert_called_once_with("global_monitor", {})
        assert state == {"existing": True}

        monitor.save_state({"new": True})
        mock_write.assert_called_once_with("global_monitor", {"new": True})

    @patch('hooks.hook_utils.base.get_session_id')
    @patch('hooks.hook_utils.base.read_session_state')
    @patch('hooks.hook_utils.base.write_session_state')
    def test_load_save_state_session(self, mock_write, mock_read, mock_get_session):
        """Session state uses session-scoped functions."""
        mock_get_session.return_value = "session123"
        mock_read.return_value = {"session_data": True}

        class SessionMonitor(MonitoringHook):
            def process(self, ctx, state):
                return state, None

        monitor = SessionMonitor("session_monitor", use_session=True)
        ctx = {"session_id": "session123"}
        state = monitor.load_state(ctx)

        mock_read.assert_called_once_with("session_monitor", "session123", {})
        assert state == {"session_data": True}

        monitor.save_state({"updated": True}, ctx)
        # Note: parameter order is (namespace, data, session_id)
        mock_write.assert_called_once_with("session_monitor", {"updated": True}, "session123")

    @patch('hooks.hook_utils.base.read_state')
    @patch('hooks.hook_utils.base.write_state')
    def test_callable_interface(self, mock_write, mock_read):
        """MonitoringHook should be callable and manage state."""
        mock_read.return_value = {"count": 5}

        class CallableMonitor(MonitoringHook):
            def process(self, ctx, state):
                state['count'] = state.get('count', 0) + 1
                return state, {"result": state['count']}

        monitor = CallableMonitor("callable", use_session=False)
        result = monitor({})

        assert result == {"result": 6}
        mock_write.assert_called_once()


class TestSuggestionHook:
    """Tests for SuggestionHook base class."""

    def test_suggest_once_only(self):
        """Same suggestion should only be made once."""
        class Advisor(SuggestionHook):
            def get_suggestion(self, ctx):
                return ("key1", "Try this!")

        advisor = Advisor("advisor")

        # First call should suggest
        result1 = advisor({})
        assert result1 is not None
        assert "Try this!" in result1["hookSpecificOutput"]["message"]

        # Second call with same key should not suggest
        result2 = advisor({})
        assert result2 is None

    def test_different_keys_suggest_multiple(self):
        """Different keys should allow multiple suggestions."""
        class MultiAdvisor(SuggestionHook):
            def __init__(self):
                super().__init__("multi")
                self.suggestion_count = 0

            def get_suggestion(self, ctx):
                self.suggestion_count += 1
                return (f"key{self.suggestion_count}", f"Suggestion {self.suggestion_count}")

        advisor = MultiAdvisor()

        result1 = advisor({})
        result2 = advisor({})

        assert result1 is not None
        assert result2 is not None
        assert "Suggestion 1" in result1["hookSpecificOutput"]["message"]
        assert "Suggestion 2" in result2["hookSpecificOutput"]["message"]

    def test_no_suggestion_returns_none(self):
        """Returning None from get_suggestion() means no suggestion."""
        class QuietAdvisor(SuggestionHook):
            def get_suggestion(self, ctx):
                return None

        advisor = QuietAdvisor("quiet")
        assert advisor({}) is None

    def test_message_builder(self):
        """message() should build proper response structure."""
        class MsgAdvisor(SuggestionHook):
            def get_suggestion(self, ctx):
                return None

        advisor = MsgAdvisor("msg")
        result = advisor.message("Test message", "CustomEvent")

        assert result == {
            "hookSpecificOutput": {
                "hookEventName": "CustomEvent",
                "message": "Test message"
            }
        }

    def test_should_suggest_and_mark(self):
        """should_suggest and mark_suggested work correctly."""
        class ManualAdvisor(SuggestionHook):
            def get_suggestion(self, ctx):
                return None

        advisor = ManualAdvisor("manual")

        assert advisor.should_suggest("new_key") is True
        advisor.mark_suggested("new_key")
        assert advisor.should_suggest("new_key") is False
        assert advisor.should_suggest("other_key") is True


class TestStateTrackingHook:
    """Tests for StateTrackingHook base class."""

    def test_inherits_from_monitoring_hook(self):
        """StateTrackingHook should inherit from MonitoringHook."""
        assert issubclass(StateTrackingHook, MonitoringHook)

    def test_increment_helper(self):
        """increment() should increase counter in state."""
        state = {}

        result1 = StateTrackingHook.increment(state, "calls")
        assert result1 == 1
        assert state["calls"] == 1

        result2 = StateTrackingHook.increment(state, "calls")
        assert result2 == 2
        assert state["calls"] == 2

        result3 = StateTrackingHook.increment(state, "calls", 5)
        assert result3 == 7
        assert state["calls"] == 7

    def test_record_timestamp(self):
        """record_timestamp() should store ISO format timestamp."""
        state = {}

        ts = StateTrackingHook.record_timestamp(state, "last_seen")

        assert "last_seen" in state
        assert state["last_seen"] == ts
        # Should be ISO format: YYYY-MM-DDTHH:MM:SS...
        assert "T" in ts
        assert len(ts) >= 19  # At minimum YYYY-MM-DDTHH:MM:SS

    def test_get_count_helper(self):
        """get_count() should return counter value or 0."""
        state = {"existing": 42}

        assert StateTrackingHook.get_count(state, "existing") == 42
        assert StateTrackingHook.get_count(state, "missing") == 0

    @patch('hooks.hook_utils.base.read_state')
    @patch('hooks.hook_utils.base.write_state')
    def test_process_delegates_to_subclass(self, mock_write, mock_read):
        """process() should call should_track and track_event."""
        mock_read.return_value = {}

        class Tracker(StateTrackingHook):
            def should_track(self, ctx):
                return ctx.get("track", False)

            def track_event(self, ctx, state):
                self.increment(state, "tracked")
                return state

        tracker = Tracker("tracker", use_session=False)

        # Should not track
        state1, _ = tracker.process({"track": False}, {})
        assert "tracked" not in state1

        # Should track
        state2, _ = tracker.process({"track": True}, {})
        assert state2["tracked"] == 1

    @patch('hooks.hook_utils.base.read_state')
    @patch('hooks.hook_utils.base.write_state')
    def test_callable_interface(self, mock_write, mock_read):
        """StateTrackingHook should be callable via MonitoringHook."""
        mock_read.return_value = {"events": 0}

        class EventTracker(StateTrackingHook):
            def should_track(self, ctx):
                return True

            def track_event(self, ctx, state):
                self.increment(state, "events")
                return state

        tracker = EventTracker("events", use_session=False)
        result = tracker({})

        # Returns None (no response)
        assert result is None
        # But state should have been updated and saved
        mock_write.assert_called_once()
        saved_state = mock_write.call_args[0][1]
        assert saved_state["events"] == 1

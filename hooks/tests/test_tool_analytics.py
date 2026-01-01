#!/usr/bin/env python3
"""Unit tests for tool_analytics.py functions.

Tests for consolidated tool tracking, token monitoring, and failure detection.
"""

import sys
import time
import tempfile
import json
from pathlib import Path
from datetime import datetime
from unittest import TestCase, main
from unittest.mock import patch, MagicMock

from hooks.handlers.tool_analytics import (
    extract_error_info,
    match_error_pattern,
    track_success,
    track_tokens,
    check_output_size,
    get_daily_log_path,
    load_daily_stats,
    save_daily_stats,
    load_tracker_state,
    save_tracker_state,
    track_tool_analytics,
    ERROR_PATTERNS,
    TOOL_ALTERNATIVES,
    FAILURE_THRESHOLD,
    OUTPUT_WARNING_THRESHOLD,
    OUTPUT_CRITICAL_THRESHOLD,
    DAILY_WARNING_THRESHOLD,
)
from hooks.hook_sdk import PostToolUseContext


class TestExtractErrorInfo(TestCase):
    """Tests for extract_error_info function."""

    def test_string_result(self):
        """String results are treated as non-error with the string as message."""
        is_error, msg = extract_error_info("test output")
        self.assertFalse(is_error)
        self.assertEqual(msg, "test output")

    def test_string_truncation(self):
        """Long strings are truncated to 500 chars."""
        long_string = "x" * 1000
        is_error, msg = extract_error_info(long_string)
        self.assertFalse(is_error)
        self.assertEqual(len(msg), 500)

    def test_dict_with_error_flag(self):
        """Dict with is_error=True extracts error status."""
        result = {"is_error": True, "content": "error message"}
        is_error, msg = extract_error_info(result)
        self.assertTrue(is_error)
        self.assertEqual(msg, "error message")

    def test_dict_without_error_flag(self):
        """Dict without is_error is treated as non-error."""
        result = {"content": "success message"}
        is_error, msg = extract_error_info(result)
        self.assertFalse(is_error)
        self.assertEqual(msg, "success message")

    def test_dict_with_list_content(self):
        """Dict with list content concatenates text items."""
        result = {
            "is_error": False,
            "content": [
                {"text": "line 1\n"},
                {"text": "line 2\n"},
                {"other": "ignored"}
            ]
        }
        is_error, msg = extract_error_info(result)
        self.assertFalse(is_error)
        self.assertIn("line 1", msg)
        self.assertIn("line 2", msg)

    def test_empty_result(self):
        """Empty or None results return empty message."""
        is_error, msg = extract_error_info(None)
        self.assertFalse(is_error)
        self.assertEqual(msg, "")

    def test_non_dict_non_string(self):
        """Non-dict, non-string results are converted to string."""
        is_error, msg = extract_error_info(12345)
        self.assertFalse(is_error)
        self.assertEqual(msg, "12345")


class TestMatchErrorPattern(TestCase):
    """Tests for match_error_pattern function."""

    def test_edit_tool_old_string_not_found(self):
        """Edit tool 'old_string not found' error matches pattern."""
        msg = "Error: old_string not found in file"
        result = match_error_pattern(msg)
        self.assertIsNotNone(result)
        self.assertEqual(result["tool"], "Edit")
        self.assertIn("Re-read", result["suggestion"])
        self.assertEqual(result["action"], "read_first")

    def test_file_not_found(self):
        """File not found errors match pattern."""
        msg = "Error: file not found: /path/to/file"
        result = match_error_pattern(msg)
        self.assertIsNotNone(result)
        self.assertIn("smart-find", result["suggestion"])
        self.assertEqual(result["action"], "find_file")

    def test_permission_denied(self):
        """Permission denied errors match pattern."""
        msg = "permission denied: cannot access file"
        result = match_error_pattern(msg)
        self.assertIsNotNone(result)
        self.assertIn("permissions", result["suggestion"])
        self.assertEqual(result["action"], "check_perms")

    def test_grep_no_matches(self):
        """Grep 'no matches' error matches pattern."""
        msg = "no results found for pattern"
        result = match_error_pattern(msg)
        self.assertIsNotNone(result)
        # Note: "no matches" pattern matches before Grep-specific pattern
        # so we just verify we get a suggestion
        self.assertIn("suggestion", result)

    def test_build_failed(self):
        """Build failure errors match pattern."""
        msg = "make: *** [target] Error 1"
        result = match_error_pattern(msg)
        self.assertIsNotNone(result)
        self.assertEqual(result["tool"], "Bash")
        self.assertIn("compress", result["suggestion"])
        self.assertEqual(result["action"], "compress_output")

    def test_test_failed(self):
        """Test failure errors match pattern."""
        msg = "pytest failed: 3 tests failed"
        result = match_error_pattern(msg)
        self.assertIsNotNone(result)
        self.assertIn("compress", result["suggestion"])

    def test_timeout(self):
        """Timeout errors match pattern."""
        msg = "Command timed out after 30s"
        result = match_error_pattern(msg)
        self.assertIsNotNone(result)
        self.assertIn("limiting scope", result["suggestion"])
        self.assertEqual(result["action"], "reduce_scope")

    def test_case_insensitive(self):
        """Pattern matching is case-insensitive."""
        msg = "PERMISSION DENIED"
        result = match_error_pattern(msg)
        self.assertIsNotNone(result)
        self.assertEqual(result["action"], "check_perms")

    def test_no_match(self):
        """Non-error messages return None."""
        msg = "Everything is fine"
        result = match_error_pattern(msg)
        self.assertIsNone(result)


class TestGetDailyLogPath(TestCase):
    """Tests for get_daily_log_path function."""

    def test_returns_path_with_today_date(self):
        """Daily log path includes today's date."""
        path = get_daily_log_path()
        today = datetime.now().strftime("%Y-%m-%d")
        self.assertIn(today, str(path))
        self.assertTrue(str(path).endswith(".json"))

    def test_path_includes_tracker_dir(self):
        """Daily log path is in TRACKER_DIR."""
        path = get_daily_log_path()
        self.assertIn("tracking", str(path))


class TestLoadSaveTrackerState(TestCase):
    """Tests for load_tracker_state and save_tracker_state."""

    @patch("hooks.handlers.tool_analytics.read_session_state")
    def test_load_tracker_state_default(self, mock_read):
        """Loading tracker state returns default if no state exists."""
        mock_read.return_value = {"failures": {}, "last_update": time.time()}
        state = load_tracker_state("test-session")
        self.assertIn("failures", state)
        self.assertIn("last_update", state)
        self.assertEqual(state["failures"], {})

    @patch("hooks.handlers.tool_analytics.read_session_state")
    def test_load_tracker_state_expired(self, mock_read):
        """Expired tracker state returns default."""
        old_time = time.time() - (7 * 24 * 3600 + 1)  # Over 7 days old
        mock_read.return_value = {
            "failures": {"Edit": {"count": 5}},
            "last_update": old_time
        }
        state = load_tracker_state("test-session")
        self.assertEqual(state["failures"], {})  # Reset to default

    @patch("hooks.handlers.tool_analytics.write_session_state")
    def test_save_tracker_state(self, mock_write):
        """Saving tracker state updates timestamp."""
        state = {"failures": {"Edit": {"count": 3}}}
        save_tracker_state("test-session", state)
        self.assertIn("last_update", state)
        mock_write.assert_called_once()


class TestLoadSaveDailyStats(TestCase):
    """Tests for load_daily_stats and save_daily_stats."""

    def test_load_daily_stats_default(self):
        """Loading daily stats returns default structure."""
        # Clear cache first
        from hooks.handlers.tool_analytics import _daily_stats_cache
        _daily_stats_cache.clear()

        with patch("hooks.handlers.tool_analytics.safe_load_json") as mock_load:
            mock_load.return_value = {
                "date": datetime.now().strftime("%Y-%m-%d"),
                "total_tokens": 0,
                "tool_calls": 0,
                "by_tool": {},
                "sessions": 0,
            }
            stats = load_daily_stats()
            self.assertEqual(stats["total_tokens"], 0)
            self.assertEqual(stats["tool_calls"], 0)
            self.assertIsInstance(stats["by_tool"], dict)

    @patch("hooks.handlers.tool_analytics.safe_load_json")
    def test_load_daily_stats_cached(self, mock_load):
        """Cached daily stats avoid file I/O."""
        mock_load.return_value = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "total_tokens": 1000,
            "tool_calls": 10,
            "by_tool": {},
            "sessions": 1,
        }
        # First load - cache miss
        stats1 = load_daily_stats()
        # Second load - cache hit (mock shouldn't be called again)
        stats2 = load_daily_stats()
        self.assertEqual(stats1["total_tokens"], stats2["total_tokens"])

    @patch("hooks.handlers.tool_analytics.safe_save_json")
    def test_save_daily_stats_batching(self, mock_save):
        """Daily stats are only saved periodically based on flush interval."""
        from hooks.handlers.tool_analytics import Thresholds
        stats = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "total_tokens": 1000,
            "tool_calls": Thresholds.STATS_FLUSH_INTERVAL - 1,  # Not a flush interval
            "by_tool": {},
            "sessions": 1,
        }
        save_daily_stats(stats, force=False)
        mock_save.assert_not_called()

    @patch("hooks.handlers.tool_analytics.safe_save_json")
    def test_save_daily_stats_force(self, mock_save):
        """Forcing save writes immediately."""
        stats = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "total_tokens": 100,
            "tool_calls": 1,
            "by_tool": {},
            "sessions": 1,
        }
        save_daily_stats(stats, force=True)
        mock_save.assert_called_once()


class TestTrackSuccess(TestCase):
    """Tests for track_success function."""

    @patch("hooks.handlers.tool_analytics.load_tracker_state")
    @patch("hooks.handlers.tool_analytics.save_tracker_state")
    @patch("hooks.handlers.tool_analytics.get_session_id")
    def test_successful_tool_resets_failure_count(self, mock_session, mock_save, mock_load):
        """Successful tool execution resets failure count."""
        mock_session.return_value = "test-session"
        mock_load.return_value = {
            "failures": {
                "Edit": {"count": 5, "recent_errors": [], "last_success": 0}
            },
            "last_update": time.time()
        }

        raw = {
            "tool_name": "Edit",
            "tool_input": {"file_path": "test.txt"},
            "tool_result": {"content": "success"}
        }
        ctx = PostToolUseContext(raw)
        messages = track_success(ctx)

        # Should reset count on success
        saved_state = mock_save.call_args[0][1]
        self.assertEqual(saved_state["failures"]["Edit"]["count"], 0)

    @patch("hooks.handlers.tool_analytics.load_tracker_state")
    @patch("hooks.handlers.tool_analytics.save_tracker_state")
    @patch("hooks.handlers.tool_analytics.get_session_id")
    def test_error_pattern_match_generates_suggestion(self, mock_session, mock_save, mock_load):
        """Matching error pattern generates immediate suggestion."""
        mock_session.return_value = "test-session"
        mock_load.return_value = {"failures": {}, "last_update": time.time()}

        raw = {
            "tool_name": "Edit",
            "tool_input": {"file_path": "test.txt"},
            "tool_result": {"is_error": True, "content": "old_string not found"}
        }
        ctx = PostToolUseContext(raw)
        messages = track_success(ctx)

        self.assertTrue(len(messages) > 0)
        self.assertTrue(any("Suggestion" in msg for msg in messages))
        self.assertTrue(any("Re-read" in msg for msg in messages))

    @patch("hooks.handlers.tool_analytics.load_tracker_state")
    @patch("hooks.handlers.tool_analytics.save_tracker_state")
    @patch("hooks.handlers.tool_analytics.get_session_id")
    def test_repeated_failures_suggest_alternative(self, mock_session, mock_save, mock_load):
        """Repeated failures trigger alternative suggestion."""
        mock_session.return_value = "test-session"
        mock_load.return_value = {
            "failures": {
                "Grep": {"count": FAILURE_THRESHOLD - 1, "recent_errors": [], "last_success": 0}
            },
            "last_update": time.time()
        }

        raw = {
            "tool_name": "Grep",
            "tool_input": {"pattern": "test"},
            "tool_result": {"is_error": True, "content": "some error"}
        }
        ctx = PostToolUseContext(raw)
        messages = track_success(ctx)

        self.assertTrue(len(messages) > 0)
        self.assertTrue(any("Alternative" in msg for msg in messages))


class TestTrackTokens(TestCase):
    """Tests for track_tokens function."""

    @patch("hooks.handlers.tool_analytics.load_daily_stats")
    @patch("hooks.handlers.tool_analytics.save_daily_stats")
    def test_tracks_token_usage(self, mock_save, mock_load):
        """Token tracking updates daily stats."""
        mock_load.return_value = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "total_tokens": 0,
            "tool_calls": 0,
            "by_tool": {},
            "sessions": 0,
        }

        raw = {
            "tool_name": "Read",
            "tool_input": {"file_path": "test.txt"},
            "tool_result": {"content": "x" * 1000}  # ~250 tokens
        }
        ctx = PostToolUseContext(raw)
        messages = track_tokens(ctx)

        # Should have updated stats
        saved_stats = mock_save.call_args[0][0]
        self.assertGreater(saved_stats["total_tokens"], 0)
        self.assertEqual(saved_stats["tool_calls"], 1)
        self.assertIn("Read", saved_stats["by_tool"])

    def test_warns_on_threshold(self):
        """Token tracking warns when threshold is exceeded."""
        # Clear cache first
        from hooks.handlers.tool_analytics import _daily_stats_cache
        _daily_stats_cache.clear()

        with patch("hooks.handlers.tool_analytics.load_daily_stats") as mock_load, \
             patch("hooks.handlers.tool_analytics.save_daily_stats") as mock_save:
            # Set up stats that exceed threshold and will trigger warning
            # (tool_calls increments to 50 after this call)
            mock_load.return_value = {
                "date": datetime.now().strftime("%Y-%m-%d"),
                "total_tokens": DAILY_WARNING_THRESHOLD,
                "tool_calls": 49,  # Will become 50 after this call
                "by_tool": {"Read": 500000},
                "sessions": 1,
            }

            raw = {
                "tool_name": "Read",
                "tool_input": {"file_path": "test.txt"},
                "tool_result": {"content": "test"}
            }
            ctx = PostToolUseContext(raw)
            messages = track_tokens(ctx)

            # Should warn about high token usage
            self.assertTrue(len(messages) > 0)
            self.assertTrue(any("Daily usage" in msg for msg in messages))


class TestCheckOutputSize(TestCase):
    """Tests for check_output_size function."""

    def test_small_output_no_warning(self):
        """Small output returns no warnings."""
        raw = {
            "tool_name": "Read",
            "tool_input": {"file_path": "test.txt"},
            "tool_result": {"content": "small output"}
        }
        ctx = PostToolUseContext(raw)
        messages = check_output_size(ctx)
        self.assertEqual(len(messages), 0)

    def test_warning_threshold(self):
        """Output at warning threshold generates message."""
        # Create output that exceeds warning threshold
        large_content = "x" * (OUTPUT_WARNING_THRESHOLD + 1000)
        raw = {
            "tool_name": "Read",
            "tool_input": {"file_path": "test.txt"},
            "tool_result": {"content": large_content}
        }
        ctx = PostToolUseContext(raw)
        messages = check_output_size(ctx)

        self.assertTrue(len(messages) > 0)
        self.assertTrue(any("Output Monitor" in msg for msg in messages))

    def test_critical_threshold(self):
        """Output at critical threshold generates detailed warning."""
        critical_content = "x" * (OUTPUT_CRITICAL_THRESHOLD + 1000)
        raw = {
            "tool_name": "Read",
            "tool_input": {"file_path": "test.txt"},
            "tool_result": {"content": critical_content}
        }
        ctx = PostToolUseContext(raw)
        messages = check_output_size(ctx)

        self.assertTrue(len(messages) > 0)
        self.assertTrue(any("Large output" in msg for msg in messages))
        self.assertTrue(any("compression" in msg.lower() for msg in messages))

    def test_bash_tool_specific_suggestions(self):
        """Bash tool gets specific compression suggestions."""
        critical_content = "x" * (OUTPUT_CRITICAL_THRESHOLD + 1000)
        raw = {
            "tool_name": "Bash",
            "tool_input": {"command": "cat large.log"},
            "tool_result": critical_content
        }
        ctx = PostToolUseContext(raw)
        messages = check_output_size(ctx)

        self.assertTrue(any("head" in msg or "compress" in msg for msg in messages))

    def test_grep_tool_specific_suggestions(self):
        """Grep tool gets head_limit suggestion."""
        critical_content = "x" * (OUTPUT_CRITICAL_THRESHOLD + 1000)
        raw = {
            "tool_name": "Grep",
            "tool_input": {"pattern": "test"},
            "tool_result": critical_content
        }
        ctx = PostToolUseContext(raw)
        messages = check_output_size(ctx)

        self.assertTrue(any("head_limit" in msg for msg in messages))

    def test_read_tool_specific_suggestions(self):
        """Read tool gets smart-view.sh suggestion."""
        critical_content = "x" * (OUTPUT_CRITICAL_THRESHOLD + 1000)
        raw = {
            "tool_name": "Read",
            "tool_input": {"file_path": "test.txt"},
            "tool_result": critical_content
        }
        ctx = PostToolUseContext(raw)
        messages = check_output_size(ctx)

        self.assertTrue(any("smart-view" in msg for msg in messages))

    def test_large_output_tools_higher_threshold(self):
        """Tools in LARGE_OUTPUT_TOOLS have 3x threshold."""
        from hooks.handlers.tool_analytics import LARGE_OUTPUT_TOOLS

        # Use Task which is definitely in LARGE_OUTPUT_TOOLS
        # Content that would warn for normal tools but not large output tools
        content = "x" * (OUTPUT_WARNING_THRESHOLD + 1000)
        raw = {
            "tool_name": "Task",  # In LARGE_OUTPUT_TOOLS
            "tool_input": {"prompt": "test"},
            "tool_result": content
        }
        ctx = PostToolUseContext(raw)
        messages = check_output_size(ctx)

        # Should not warn yet (3x threshold)
        self.assertEqual(len(messages), 0)


class TestTrackToolAnalytics(TestCase):
    """Tests for track_tool_analytics combined handler."""

    @patch("hooks.handlers.tool_analytics.track_success")
    @patch("hooks.handlers.tool_analytics.track_tokens")
    @patch("hooks.handlers.tool_analytics.check_output_size")
    def test_combines_all_trackers(self, mock_size, mock_tokens, mock_success):
        """Combined handler calls all tracking functions."""
        mock_success.return_value = []
        mock_tokens.return_value = []
        mock_size.return_value = []

        raw = {
            "tool_name": "Read",
            "tool_input": {"file_path": "test.txt"},
            "tool_result": {"content": "test"}
        }
        result = track_tool_analytics(raw)

        mock_success.assert_called_once()
        mock_tokens.assert_called_once()
        mock_size.assert_called_once()

    @patch("hooks.handlers.tool_analytics.track_success")
    @patch("hooks.handlers.tool_analytics.track_tokens")
    @patch("hooks.handlers.tool_analytics.check_output_size")
    def test_limits_messages_to_three(self, mock_size, mock_tokens, mock_success):
        """Combined handler limits output to 3 messages."""
        mock_success.return_value = ["msg1", "msg2"]
        mock_tokens.return_value = ["msg3"]
        mock_size.return_value = ["msg4", "msg5"]

        raw = {
            "tool_name": "Read",
            "tool_input": {"file_path": "test.txt"},
            "tool_result": {"content": "test"}
        }
        result = track_tool_analytics(raw)

        self.assertIsNotNone(result)
        msg = result["hookSpecificOutput"]["message"]
        # Should only have 3 messages (limited by [:3])
        parts = msg.split(" | ")
        self.assertEqual(len(parts), 3)

    @patch("hooks.handlers.tool_analytics.track_success")
    @patch("hooks.handlers.tool_analytics.track_tokens")
    @patch("hooks.handlers.tool_analytics.check_output_size")
    def test_returns_none_when_no_messages(self, mock_size, mock_tokens, mock_success):
        """Combined handler returns None when no messages."""
        mock_success.return_value = []
        mock_tokens.return_value = []
        mock_size.return_value = []

        raw = {
            "tool_name": "Read",
            "tool_input": {"file_path": "test.txt"},
            "tool_result": {"content": "test"}
        }
        result = track_tool_analytics(raw)

        self.assertIsNone(result)


if __name__ == "__main__":
    main()

"""Tests for hook_sdk module."""
import sys
import threading
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from hooks.hook_sdk import detect_event, RateLimiter, EventType


class TestDetectEvent:
    """Tests for detect_event function."""

    def test_detect_post_tool_use_with_tool_response(self):
        """Should detect PostToolUse when tool_response present."""
        ctx = {"tool_name": "Bash", "tool_response": "output"}
        assert detect_event(ctx) == "PostToolUse"

    def test_detect_post_tool_use_with_tool_result(self):
        """Should detect PostToolUse when tool_result present."""
        ctx = {"tool_name": "Read", "tool_result": "content"}
        assert detect_event(ctx) == "PostToolUse"

    def test_detect_pre_compact(self):
        """Should detect PreCompact when transcript_path present without tool_name."""
        ctx = {"transcript_path": "/path/to/transcript.json"}
        assert detect_event(ctx) == "PreCompact"

    def test_detect_session_start(self):
        """Should detect SessionStart with event field."""
        ctx = {"event": "SessionStart", "cwd": "/project"}
        assert detect_event(ctx) == "SessionStart"

    def test_detect_session_end(self):
        """Should detect SessionEnd with event field."""
        ctx = {"event": "SessionEnd"}
        assert detect_event(ctx) == "SessionEnd"

    def test_detect_pre_tool_use_default(self):
        """Should detect PreToolUse for tool_name without response."""
        ctx = {"tool_name": "Write", "tool_input": {"content": "..."}}
        assert detect_event(ctx) == "PreToolUse"

    def test_detect_pre_tool_use_for_empty(self):
        """Should return PreToolUse for empty context (default)."""
        ctx = {}
        assert detect_event(ctx) == "PreToolUse"

    def test_detect_user_prompt_submit(self):
        """Should detect UserPromptSubmit when user_prompt present."""
        ctx = {"user_prompt": "hello"}
        assert detect_event(ctx) == "UserPromptSubmit"

    def test_detect_stop(self):
        """Should detect Stop event."""
        ctx = {"event": "Stop"}
        assert detect_event(ctx) == "Stop"


class TestRateLimiter:
    """Tests for thread-safe RateLimiter with state persistence."""

    def test_rate_limiter_allows_within_limit(self, tmp_path):
        """Should allow requests within rate limit."""
        with patch('hooks.hook_sdk.read_state', return_value={"timestamps": []}):
            with patch('hooks.hook_sdk.write_state'):
                limiter = RateLimiter("test1", max_count=3, window_secs=1)
                assert limiter.consume() is True

    def test_rate_limiter_blocks_over_limit(self, tmp_path):
        """Should block requests exceeding rate limit."""
        now = time.time()
        with patch('hooks.hook_sdk.read_state', return_value={"timestamps": [now, now]}):
            with patch('hooks.hook_sdk.write_state'):
                limiter = RateLimiter("test2", max_count=2, window_secs=1)
                assert limiter.consume() is False

    def test_rate_limiter_check_doesnt_consume(self, tmp_path):
        """check() should not consume quota."""
        with patch('hooks.hook_sdk.read_state', return_value={"timestamps": []}):
            limiter = RateLimiter("test3", max_count=1, window_secs=1)
            assert limiter.check() is True
            assert limiter.check() is True  # Still true, didn't consume

    def test_rate_limiter_expires_old_timestamps(self, tmp_path):
        """Should expire timestamps older than window."""
        old_time = time.time() - 100  # Very old
        with patch('hooks.hook_sdk.read_state', return_value={"timestamps": [old_time, old_time]}):
            with patch('hooks.hook_sdk.write_state'):
                limiter = RateLimiter("test4", max_count=2, window_secs=1)
                assert limiter.consume() is True  # Old timestamps expired

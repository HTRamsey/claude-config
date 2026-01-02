"""Tests for handlers/auto_continue.py"""
import json
import tempfile
import time
from pathlib import Path
from unittest.mock import patch, Mock

import pytest


class TestAutoContinue:
    """Tests for auto-continue handler."""

    def test_check_rate_limit_no_continuations(self):
        from hooks.handlers.auto_continue import check_rate_limit
        with patch("hooks.handlers.auto_continue.load_continue_state") as mock_load:
            mock_load.return_value = {"continuations": [], "last_reset": time.time()}
            assert check_rate_limit() is True

    def test_extract_last_messages_from_context(self):
        from hooks.handlers.auto_continue import extract_last_messages
        ctx = {"messages": [{"type": "user", "content": "hello"}]}
        result = extract_last_messages(ctx, count=5)
        assert len(result) == 1

    def test_heuristic_should_continue_empty(self):
        from hooks.handlers.auto_continue import heuristic_should_continue
        should, reason = heuristic_should_continue([])
        assert should is False
        assert "no messages" in reason

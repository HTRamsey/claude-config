"""Tests for handlers/viewer.py"""
from pathlib import Path
from unittest.mock import patch

import pytest


class TestViewer:
    """Tests for viewer handler."""

    def test_is_viewer_running_no_pid(self):
        from hooks.handlers.viewer import is_viewer_running
        # Mock PID_FILE.exists() to return False
        with patch.object(Path, 'exists', return_value=False):
            result = is_viewer_running()
            assert result is False

    def test_maybe_start_viewer_already_running(self):
        from hooks.handlers import viewer
        with patch.object(viewer, 'is_viewer_running', return_value=True):
            result = viewer.maybe_start_viewer()
            assert result is None

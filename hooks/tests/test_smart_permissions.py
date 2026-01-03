#!/home/jonglaser/.claude/data/venv/bin/python3
"""
Tests for SmartPermissionsHandler (PostToolUse handler for permission learning).
"""
from unittest import TestCase
from unittest.mock import patch, MagicMock


class TestSmartPermissionsHandler(TestCase):
    """Tests for SmartPermissionsHandler."""

    def test_handler_has_correct_tools(self):
        """Handler should only apply to Read, Edit, Write."""
        from hooks.handlers.smart_permissions import SmartPermissionsHandler

        handler = SmartPermissionsHandler()
        self.assertEqual(handler.tools, ["Read", "Edit", "Write"])

    def test_handler_event_is_post_tool_use(self):
        """Handler should be PostToolUse event."""
        from hooks.handlers.smart_permissions import SmartPermissionsHandler

        handler = SmartPermissionsHandler()
        self.assertEqual(handler.event, "PostToolUse")

    @patch("hooks.handlers.smart_permissions.record_approval")
    @patch("hooks.handlers.smart_permissions.get_never_patterns")
    def test_records_approval_for_read(self, mock_never, mock_record):
        """Should record approval for Read operations."""
        mock_never.return_value = []

        from hooks.handlers.smart_permissions import smart_permissions_post

        raw = {
            "tool_name": "Read",
            "tool_input": {"file_path": "/home/user/project/src/main.py"},
        }
        result = smart_permissions_post(raw)

        self.assertIsNone(result)
        mock_record.assert_called_once_with("Read", "/home/user/project/src/main.py")

    @patch("hooks.handlers.smart_permissions.record_approval")
    @patch("hooks.handlers.smart_permissions.get_never_patterns")
    def test_records_approval_for_edit(self, mock_never, mock_record):
        """Should record approval for Edit operations."""
        mock_never.return_value = []

        from hooks.handlers.smart_permissions import smart_permissions_post

        raw = {
            "tool_name": "Edit",
            "tool_input": {"file_path": "/home/user/test.py"},
        }
        result = smart_permissions_post(raw)

        self.assertIsNone(result)
        mock_record.assert_called_once_with("Edit", "/home/user/test.py")

    @patch("hooks.handlers.smart_permissions.record_approval")
    @patch("hooks.handlers.smart_permissions.get_never_patterns")
    def test_records_approval_for_write(self, mock_never, mock_record):
        """Should record approval for Write operations."""
        mock_never.return_value = []

        from hooks.handlers.smart_permissions import smart_permissions_post

        raw = {
            "tool_name": "Write",
            "tool_input": {"file_path": "/home/user/new_file.py"},
        }
        result = smart_permissions_post(raw)

        self.assertIsNone(result)
        mock_record.assert_called_once_with("Write", "/home/user/new_file.py")

    @patch("hooks.handlers.smart_permissions.record_approval")
    @patch("hooks.handlers.smart_permissions.get_never_patterns")
    def test_skips_empty_file_path(self, mock_never, mock_record):
        """Should skip when file_path is empty."""
        mock_never.return_value = []

        from hooks.handlers.smart_permissions import smart_permissions_post

        raw = {
            "tool_name": "Read",
            "tool_input": {"file_path": ""},
        }
        result = smart_permissions_post(raw)

        self.assertIsNone(result)
        mock_record.assert_not_called()

    @patch("hooks.handlers.smart_permissions.record_approval")
    @patch("hooks.handlers.smart_permissions.get_never_patterns")
    def test_skips_missing_file_path(self, mock_never, mock_record):
        """Should skip when file_path is missing."""
        mock_never.return_value = []

        from hooks.handlers.smart_permissions import smart_permissions_post

        raw = {
            "tool_name": "Read",
            "tool_input": {},
        }
        result = smart_permissions_post(raw)

        self.assertIsNone(result)
        mock_record.assert_not_called()

    @patch("hooks.handlers.smart_permissions.record_approval")
    def test_skips_sensitive_files(self, mock_record):
        """Should not record approval for sensitive files."""
        import re

        # Mock never patterns to include .env files
        with patch("hooks.handlers.smart_permissions.get_never_patterns") as mock_never:
            mock_never.return_value = [re.compile(r"\.env")]

            from hooks.handlers.smart_permissions import smart_permissions_post

            raw = {
                "tool_name": "Read",
                "tool_input": {"file_path": "/home/user/.env"},
            }
            result = smart_permissions_post(raw)

            self.assertIsNone(result)
            mock_record.assert_not_called()

    def test_handler_applies_to_correct_tools(self):
        """Handler applies() should filter by tool correctly."""
        from hooks.handlers.smart_permissions import SmartPermissionsHandler
        from hooks.hook_sdk import PostToolUseContext

        handler = SmartPermissionsHandler()

        # Should apply
        for tool in ["Read", "Edit", "Write"]:
            ctx = PostToolUseContext({"tool_name": tool})
            self.assertTrue(handler.applies(ctx), f"Should apply to {tool}")

        # Should not apply
        for tool in ["Bash", "Grep", "Glob", "Task"]:
            ctx = PostToolUseContext({"tool_name": tool})
            self.assertFalse(handler.applies(ctx), f"Should not apply to {tool}")

    @patch("hooks.handlers.smart_permissions.record_approval")
    @patch("hooks.handlers.smart_permissions.get_never_patterns")
    def test_callable_interface(self, mock_never, mock_record):
        """Handler should work when called directly."""
        mock_never.return_value = []

        from hooks.handlers.smart_permissions import SmartPermissionsHandler

        handler = SmartPermissionsHandler()
        raw = {
            "tool_name": "Read",
            "tool_input": {"file_path": "/test/file.py"},
        }
        result = handler(raw)

        self.assertIsNone(result)
        mock_record.assert_called_once()

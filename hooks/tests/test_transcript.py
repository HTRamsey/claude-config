#!/usr/bin/env python3
"""Unit tests for transcript.py functions.

Tests for token counting, caching, and session summary generation.
"""

import sys
import time
import tempfile
import json
import os
from pathlib import Path
from unittest import TestCase, main
from unittest.mock import patch, MagicMock

from hooks.handlers.context_manager import (
    load_cache,
    save_cache,
    get_cached_count,
    update_cache,
    _count_tokens_in_entry,
    get_transcript_size,
    get_session_summary,
)


class TestLoadSaveCache(TestCase):
    """Tests for load_cache and save_cache functions."""

    @patch("hooks.handlers.context_manager.safe_load_json")
    @patch("hooks.handlers.context_manager.safe_save_json")
    def test_load_cache_from_disk(self, mock_save, mock_load):
        """Load cache reads from disk."""
        mock_load.return_value = {"transcript": {"path": "/test.jsonl", "tokens": 1000}}

        # Clear in-memory cache first
        from hooks.handlers.context_manager import _token_cache
        _token_cache.clear()

        result = load_cache()

        self.assertEqual(result["transcript"]["tokens"], 1000)
        mock_load.assert_called_once()

    @patch("hooks.handlers.context_manager.safe_load_json")
    def test_load_cache_uses_memory(self, mock_load):
        """Subsequent loads use in-memory cache."""
        mock_load.return_value = {"test": "data"}

        # Clear cache first
        from hooks.handlers.context_manager import _token_cache
        _token_cache.clear()

        # First load
        load_cache()
        mock_load.reset_mock()

        # Second load should use memory
        result = load_cache()

        self.assertEqual(result["test"], "data")
        mock_load.assert_not_called()

    @patch("hooks.handlers.context_manager.safe_save_json")
    def test_save_cache_writes_disk_and_memory(self, mock_save):
        """Save cache updates both disk and memory."""
        cache_data = {"transcript": {"tokens": 2000}}

        save_cache(cache_data)

        mock_save.assert_called_once()
        # Verify in-memory cache updated
        from hooks.handlers.context_manager import _token_cache, _TOKEN_CACHE_KEY
        self.assertEqual(_token_cache[_TOKEN_CACHE_KEY], cache_data)


class TestGetCachedCount(TestCase):
    """Tests for get_cached_count function."""

    def test_returns_none_for_missing_cache(self):
        """Returns None if no cache exists."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jsonl") as f:
            path = f.name

        try:
            with patch("hooks.handlers.context_manager.load_cache", return_value={}):
                result = get_cached_count(path)
                self.assertIsNone(result)
        finally:
            Path(path).unlink()

    def test_returns_none_for_different_path(self):
        """Returns None if cached path doesn't match."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jsonl") as f:
            path = f.name

        try:
            with patch("hooks.handlers.context_manager.load_cache") as mock_load:
                mock_load.return_value = {
                    "transcript": {"path": "/other/path.jsonl", "tokens": 1000}
                }
                result = get_cached_count(path)
                self.assertIsNone(result)
        finally:
            Path(path).unlink()

    def test_returns_exact_match_for_unchanged_file(self):
        """Returns cached count if file unchanged."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jsonl", mode='w') as f:
            f.write('{"content": "test"}\n')
            path = f.name

        try:
            stat = os.stat(path)
            with patch("hooks.handlers.context_manager.load_cache") as mock_load:
                mock_load.return_value = {
                    "transcript": {
                        "path": path,
                        "mtime": stat.st_mtime,
                        "size": stat.st_size,
                        "tokens": 100,
                        "messages": 5,
                        "offset": 50
                    }
                }
                result = get_cached_count(path)

                self.assertIsNotNone(result)
                tokens, messages, offset, can_increment = result
                self.assertEqual(tokens, 100)
                self.assertEqual(messages, 5)
                self.assertFalse(can_increment)  # Exact match, no increment needed
        finally:
            Path(path).unlink()

    def test_returns_incremental_for_grown_file(self):
        """Returns incremental scan info if file grew."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jsonl", mode='w') as f:
            f.write('{"content": "test"}\n')
            path = f.name

        try:
            # Get initial file size
            initial_stat = os.stat(path)
            initial_size = initial_stat.st_size

            # Append more data to grow file
            time.sleep(0.1)  # Ensure mtime changes
            with open(path, 'a') as f:
                f.write('{"content": "more data"}\n')

            # Clear in-memory cache first
            from hooks.handlers.context_manager import _token_cache
            _token_cache.clear()

            with patch("hooks.handlers.context_manager.load_cache") as mock_load:
                # Use actual initial size, not arbitrary 50
                mock_load.return_value = {
                    "transcript": {
                        "path": path,
                        "mtime": initial_stat.st_mtime,
                        "size": initial_size,
                        "tokens": 100,
                        "messages": 5,
                        "offset": initial_size
                    }
                }
                result = get_cached_count(path)

                self.assertIsNotNone(result)
                tokens, messages, offset, can_increment = result
                self.assertEqual(tokens, 100)
                self.assertEqual(messages, 5)
                self.assertEqual(offset, initial_size)
                self.assertTrue(can_increment)  # File grew, can do incremental
        finally:
            Path(path).unlink()

    def test_handles_missing_file(self):
        """Returns None if file doesn't exist."""
        with patch("hooks.handlers.context_manager.load_cache") as mock_load:
            mock_load.return_value = {
                "transcript": {"path": "/nonexistent.jsonl", "tokens": 100}
            }
            result = get_cached_count("/nonexistent.jsonl")
            self.assertIsNone(result)


class TestUpdateCache(TestCase):
    """Tests for update_cache function."""

    @patch("hooks.handlers.context_manager.save_cache")
    def test_updates_cache_with_new_values(self, mock_save):
        """Updates cache with new token count and file stats."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jsonl", mode='w') as f:
            f.write('{"content": "test"}\n')
            path = f.name

        try:
            update_cache(path, 200, 10, 100)

            mock_save.assert_called_once()
            saved_data = mock_save.call_args[0][0]
            self.assertEqual(saved_data["transcript"]["path"], path)
            self.assertEqual(saved_data["transcript"]["tokens"], 200)
            self.assertEqual(saved_data["transcript"]["messages"], 10)
            self.assertEqual(saved_data["transcript"]["offset"], 100)
        finally:
            Path(path).unlink()

    @patch("hooks.handlers.context_manager.save_cache")
    def test_handles_missing_file(self, mock_save):
        """Handles missing file gracefully."""
        update_cache("/nonexistent.jsonl", 100, 5, 50)
        # Should not raise, but won't save
        mock_save.assert_not_called()


class TestCountTokensInEntry(TestCase):
    """Tests for _count_tokens_in_entry function."""

    def test_counts_string_content(self):
        """Counts tokens in string content."""
        entry = {"content": "This is a test message"}
        count = _count_tokens_in_entry(entry)
        self.assertGreater(count, 0)

    def test_counts_list_content(self):
        """Counts tokens in list content with text items."""
        entry = {
            "content": [
                {"text": "First line\n"},
                {"text": "Second line\n"},
                {"other": "ignored"}
            ]
        }
        count = _count_tokens_in_entry(entry)
        self.assertGreater(count, 0)

    def test_handles_missing_content(self):
        """Returns 0 for missing content."""
        entry = {"role": "user"}
        count = _count_tokens_in_entry(entry)
        self.assertEqual(count, 0)

    def test_handles_empty_content(self):
        """Returns 0 for empty content."""
        entry = {"content": ""}
        count = _count_tokens_in_entry(entry)
        self.assertEqual(count, 0)

    def test_ignores_non_text_list_items(self):
        """Ignores list items without 'text' key."""
        entry = {
            "content": [
                {"image": "base64data"},
                {"other": "data"}
            ]
        }
        count = _count_tokens_in_entry(entry)
        self.assertEqual(count, 0)


class TestGetTranscriptSize(TestCase):
    """Tests for get_transcript_size function."""

    def test_returns_zero_for_invalid_path(self):
        """Returns (0, 0) for missing or empty path."""
        test_cases = [
            ("/nonexistent.jsonl", 0, 0),
            ("", 0, 0),
        ]
        for path, expected_tokens, expected_messages in test_cases:
            with self.subTest(path=path):
                tokens, messages = get_transcript_size(path)
                self.assertEqual(tokens, expected_tokens)
                self.assertEqual(messages, expected_messages)

    def test_uses_cache_for_unchanged_file(self):
        """Uses cached values for unchanged file."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jsonl", mode='w') as f:
            f.write('{"content": "test"}\n')
            path = f.name

        try:
            stat = os.stat(path)
            with patch("hooks.handlers.context_manager.get_cached_count") as mock_cache:
                mock_cache.return_value = (1000, 50, 100, False)  # can_increment=False

                tokens, messages = get_transcript_size(path)

                self.assertEqual(tokens, 1000)
                self.assertEqual(messages, 50)
        finally:
            Path(path).unlink()

    def test_incremental_scan_for_grown_file(self):
        """Performs incremental scan when file grows."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jsonl", mode='w') as f:
            # Write initial data
            f.write('{"content": "initial message"}\n')
            f.flush()
            initial_offset = f.tell()
            # Write additional data
            f.write('{"content": "new message"}\n')
            path = f.name

        try:
            with patch("hooks.handlers.context_manager.get_cached_count") as mock_cache, \
                 patch("hooks.handlers.context_manager.update_cache") as mock_update:
                # Simulate cache returning initial count with ability to increment
                mock_cache.return_value = (10, 1, initial_offset, True)

                tokens, messages = get_transcript_size(path)

                # Should have incremented from cached values
                self.assertGreater(tokens, 10)
                self.assertEqual(messages, 2)  # 1 cached + 1 new
                mock_update.assert_called_once()
        finally:
            Path(path).unlink()

    def test_fast_path_for_small_files(self):
        """Uses estimation for small files (<160KB)."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jsonl", mode='w') as f:
            # Small file (under 160KB)
            f.write('{"content": "test"}\n' * 100)
            path = f.name

        try:
            with patch("hooks.handlers.context_manager.get_cached_count", return_value=None):
                tokens, messages = get_transcript_size(path)

                # Should estimate without full scan
                self.assertGreater(tokens, 0)
                self.assertGreater(messages, 0)
        finally:
            Path(path).unlink()

    def test_full_scan_for_large_files(self):
        """Performs full scan for large files (>160KB)."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jsonl", mode='w') as f:
            # Create large file (over 160KB)
            large_content = '{"content": "' + ('x' * 1000) + '"}\n'
            for _ in range(200):  # 200KB+
                f.write(large_content)
            path = f.name

        try:
            with patch("hooks.handlers.context_manager.get_cached_count", return_value=None), \
                 patch("hooks.handlers.context_manager.update_cache") as mock_update:
                tokens, messages = get_transcript_size(path)

                # Should have done full scan
                self.assertGreater(tokens, 0)
                self.assertEqual(messages, 200)
                mock_update.assert_called_once()
        finally:
            Path(path).unlink()

    def test_handles_invalid_json_lines(self):
        """Skips invalid JSON lines gracefully."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jsonl", mode='w') as f:
            f.write('{"content": "valid"}\n')
            f.write('invalid json line\n')
            f.write('{"content": "also valid"}\n')
            path = f.name

        try:
            with patch("hooks.handlers.context_manager.get_cached_count", return_value=None):
                tokens, messages = get_transcript_size(path)

                # Should count only valid entries
                self.assertGreater(tokens, 0)
                # Fast path estimation, so can't check exact message count
        finally:
            Path(path).unlink()

    def test_caches_result_after_full_scan(self):
        """Caches result after full scan."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jsonl", mode='w') as f:
            # Large enough to trigger full scan (>160KB)
            # Write 200 lines of 1KB each = 200KB
            large_line = '{"content": "' + ('x' * 1000) + '"}\n'
            for _ in range(200):
                f.write(large_line)
            path = f.name

        try:
            with patch("hooks.handlers.context_manager.get_cached_count", return_value=None), \
                 patch("hooks.handlers.context_manager.update_cache") as mock_update:
                get_transcript_size(path)

                # Should have cached the result
                mock_update.assert_called_once()
                args = mock_update.call_args[0]
                self.assertEqual(args[0], path)  # path
                self.assertGreater(args[1], 0)  # tokens
                self.assertGreater(args[2], 0)  # messages
                self.assertGreater(args[3], 0)  # offset
        finally:
            Path(path).unlink()


class TestGetSessionSummary(TestCase):
    """Tests for get_session_summary function."""

    def test_returns_empty_for_missing_file(self):
        """Returns empty string for missing file."""
        result = get_session_summary("/nonexistent.jsonl")
        self.assertEqual(result, "")

    def test_returns_empty_for_empty_path(self):
        """Returns empty string for empty path."""
        result = get_session_summary("")
        self.assertEqual(result, "")

    def test_summarizes_edited_files(self):
        """Includes edited files in summary."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jsonl", mode='w') as f:
            f.write(json.dumps({
                "tool_name": "Edit",
                "tool_input": {"file_path": "/project/test.py"}
            }) + '\n')
            f.write(json.dumps({
                "tool_name": "Edit",
                "tool_input": {"file_path": "/project/main.py"}
            }) + '\n')
            path = f.name

        try:
            result = get_session_summary(path)

            self.assertIn("Edited:", result)
            self.assertIn("test.py", result)
            self.assertIn("main.py", result)
        finally:
            Path(path).unlink()

    def test_summarizes_created_files(self):
        """Includes written files in summary."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jsonl", mode='w') as f:
            f.write(json.dumps({
                "tool_name": "Write",
                "tool_input": {"file_path": "/project/new.py"}
            }) + '\n')
            path = f.name

        try:
            result = get_session_summary(path)

            self.assertIn("Created:", result)
            self.assertIn("new.py", result)
        finally:
            Path(path).unlink()

    def test_counts_errors(self):
        """Counts error messages."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jsonl", mode='w') as f:
            f.write(json.dumps({"content": "Error: something failed"}) + '\n')
            f.write(json.dumps({"content": "Build failed with errors"}) + '\n')
            f.write(json.dumps({"content": "Success message"}) + '\n')
            path = f.name

        try:
            result = get_session_summary(path)

            self.assertIn("Errors:", result)
            self.assertIn("2", result)
        finally:
            Path(path).unlink()

    def test_includes_top_tools(self):
        """Includes top 3 tools by usage."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jsonl", mode='w') as f:
            # Read used 5 times
            for _ in range(5):
                f.write(json.dumps({"tool_name": "Read"}) + '\n')
            # Edit used 3 times
            for _ in range(3):
                f.write(json.dumps({"tool_name": "Edit"}) + '\n')
            # Bash used 2 times
            for _ in range(2):
                f.write(json.dumps({"tool_name": "Bash"}) + '\n')
            # Grep used 1 time
            f.write(json.dumps({"tool_name": "Grep"}) + '\n')
            path = f.name

        try:
            result = get_session_summary(path)

            self.assertIn("Tools:", result)
            self.assertIn("Read:5", result)
            self.assertIn("Edit:3", result)
            self.assertIn("Bash:2", result)
            # Grep should not be included (only top 3)
            self.assertNotIn("Grep", result)
        finally:
            Path(path).unlink()

    def test_limits_edited_files_to_5(self):
        """Limits edited files list to 5."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jsonl", mode='w') as f:
            for i in range(10):
                f.write(json.dumps({
                    "tool_name": "Edit",
                    "tool_input": {"file_path": f"/project/file{i}.py"}
                }) + '\n')
            path = f.name

        try:
            result = get_session_summary(path)

            # Count how many filenames appear (max 5)
            file_count = sum(1 for i in range(10) if f"file{i}.py" in result)
            self.assertLessEqual(file_count, 5)
        finally:
            Path(path).unlink()

    def test_limits_created_files_to_3(self):
        """Limits created files list to 3."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jsonl", mode='w') as f:
            for i in range(6):
                f.write(json.dumps({
                    "tool_name": "Write",
                    "tool_input": {"file_path": f"/project/new{i}.py"}
                }) + '\n')
            path = f.name

        try:
            result = get_session_summary(path)

            # Count how many filenames appear (max 3)
            file_count = sum(1 for i in range(6) if f"new{i}.py" in result)
            self.assertLessEqual(file_count, 3)
        finally:
            Path(path).unlink()

    def test_handles_invalid_json_lines(self):
        """Handles invalid JSON lines gracefully."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jsonl", mode='w') as f:
            f.write(json.dumps({"tool_name": "Read"}) + '\n')
            f.write('invalid json\n')
            f.write(json.dumps({"tool_name": "Edit"}) + '\n')
            path = f.name

        try:
            result = get_session_summary(path)

            # Should process valid entries
            self.assertIsInstance(result, str)
        finally:
            Path(path).unlink()

    def test_returns_empty_for_no_activity(self):
        """Returns empty string if no relevant activity."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jsonl", mode='w') as f:
            f.write(json.dumps({"content": "just a message"}) + '\n')
            path = f.name

        try:
            result = get_session_summary(path)

            # No tools, files, or errors
            self.assertEqual(result, "")
        finally:
            Path(path).unlink()



if __name__ == "__main__":
    main()

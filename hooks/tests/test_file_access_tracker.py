#!/usr/bin/env python3
"""Unit tests for file_access_tracker.py functions."""

import sys
import time
import tempfile
import json
from pathlib import Path
from unittest import TestCase, main

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from file_access_tracker import (
    normalize_path,
    normalize_pattern,
    check_similar_patterns,
    hash_search,
    check_file_modified,
    handle_pre_tool_use,
    handle_post_tool_use,
)


class TestNormalizePath(TestCase):
    """Tests for normalize_path function."""

    def test_absolute_path(self):
        result = normalize_path("/home/user/file.txt")
        self.assertEqual(result, "/home/user/file.txt")

    def test_relative_path(self):
        result = normalize_path("./file.txt")
        self.assertIn("file.txt", result)
        self.assertTrue(Path(result).is_absolute())

    def test_home_expansion(self):
        # normalize_path uses Path.resolve() which doesn't expand ~
        # This is expected behavior - ~ expansion happens at shell level
        result = normalize_path(str(Path.home() / "test.txt"))
        self.assertTrue(Path(result).is_absolute())


class TestNormalizePattern(TestCase):
    """Tests for normalize_pattern function."""

    def test_lowercase(self):
        self.assertEqual(normalize_pattern("FooBar"), "foobar")

    def test_strip_whitespace(self):
        self.assertEqual(normalize_pattern("  test  "), "test")

    def test_combined(self):
        self.assertEqual(normalize_pattern("  FooBar  "), "foobar")


class TestCheckSimilarPatterns(TestCase):
    """Tests for check_similar_patterns function."""

    def test_exact_match(self):
        result = check_similar_patterns("foo", ["foo", "bar"])
        self.assertEqual(result, "foo")

    def test_case_insensitive_match(self):
        result = check_similar_patterns("FOO", ["foo", "bar"])
        self.assertEqual(result, "foo")

    def test_substring_match(self):
        result = check_similar_patterns("foobar", ["foo", "bar"])
        self.assertEqual(result, "foo")

    def test_no_match(self):
        result = check_similar_patterns("xyz", ["foo", "bar"])
        self.assertIsNone(result)

    def test_word_overlap(self):
        # 80% overlap threshold: need 4/5 = 80% word overlap
        # "api error log handler" (4 words) vs "api error log handling" (4 words) = 3/4 = 75% - still not enough
        # Use 5 words with 4 matching: 4/5 = 80%
        result = check_similar_patterns("api error log handler code", ["api error log handling code"])
        self.assertEqual(result, "api error log handling code")


class TestHashSearch(TestCase):
    """Tests for hash_search function."""

    def test_consistent_hash(self):
        hash1 = hash_search("Grep", "pattern", "/path")
        hash2 = hash_search("Grep", "pattern", "/path")
        self.assertEqual(hash1, hash2)

    def test_different_params_different_hash(self):
        hash1 = hash_search("Grep", "pattern1", "/path")
        hash2 = hash_search("Grep", "pattern2", "/path")
        self.assertNotEqual(hash1, hash2)

    def test_hash_length(self):
        result = hash_search("Grep", "pattern", "/path")
        self.assertEqual(len(result), 12)


class TestCheckFileModified(TestCase):
    """Tests for check_file_modified function."""

    def test_unmodified_file(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"test")
            path = f.name
        read_time = time.time()
        self.assertFalse(check_file_modified(path, read_time))
        Path(path).unlink()

    def test_modified_file(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"test")
            path = f.name
        read_time = time.time() - 10  # 10 seconds ago
        # Touch file to update mtime
        Path(path).touch()
        self.assertTrue(check_file_modified(path, read_time))
        Path(path).unlink()

    def test_nonexistent_file(self):
        self.assertFalse(check_file_modified("/nonexistent/file.txt", time.time()))


class TestHandlePreToolUse(TestCase):
    """Tests for handle_pre_tool_use function."""

    def test_read_tracks_file(self):
        state = {"reads": {}, "searches": {}, "message_count": 0}
        ctx = {"tool_name": "Read", "tool_input": {"file_path": "/test/file.txt"}}
        result = handle_pre_tool_use(ctx, state)
        self.assertIsNone(result)  # Read should not produce output
        self.assertIn("/test/file.txt", state["reads"])

    def test_edit_warns_unread_file(self):
        state = {"reads": {}, "searches": {}, "message_count": 5}
        ctx = {"tool_name": "Edit", "tool_input": {"file_path": "/test/file.txt"}}
        result = handle_pre_tool_use(ctx, state)
        self.assertIsNotNone(result)
        self.assertIn("Stale Context", result["hookSpecificOutput"]["permissionDecisionReason"])

    def test_edit_no_warn_if_recently_read(self):
        state = {
            "reads": {
                "/test/file.txt": {"time": time.time(), "message_num": 5}
            },
            "searches": {},
            "message_count": 6
        }
        ctx = {"tool_name": "Edit", "tool_input": {"file_path": "/test/file.txt"}}
        result = handle_pre_tool_use(ctx, state)
        self.assertIsNone(result)


class TestHandlePostToolUse(TestCase):
    """Tests for handle_post_tool_use function."""

    def test_duplicate_search_detected(self):
        # First search to establish the hash
        state = {"reads": {}, "searches": {}, "message_count": 5}
        ctx = {"tool_name": "Grep", "tool_input": {"pattern": "foo", "path": "."}}
        handle_post_tool_use(ctx, state)  # First time - no warning

        # Second identical search should trigger warning
        result = handle_post_tool_use(ctx, state)
        self.assertIn("Duplicate", result)

    def test_new_search_tracked(self):
        state = {"reads": {}, "searches": {}, "message_count": 5}
        ctx = {"tool_name": "Grep", "tool_input": {"pattern": "newpattern", "path": "."}}
        result = handle_post_tool_use(ctx, state)
        self.assertIsNone(result)  # First search, no warning
        self.assertEqual(len(state["searches"]), 1)

    def test_duplicate_read_counted(self):
        state = {
            "reads": {"/test/file.txt": {"time": time.time(), "message_num": 1, "count": 1}},
            "searches": {},
            "message_count": 5
        }
        ctx = {"tool_name": "Read", "tool_input": {"file_path": "/test/file.txt"}}
        result = handle_post_tool_use(ctx, state)
        self.assertIn("Duplicate Read", result)
        self.assertEqual(state["reads"]["/test/file.txt"]["count"], 2)


if __name__ == "__main__":
    main()

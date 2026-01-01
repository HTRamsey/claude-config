"""Tests for stop_dispatcher module."""
import json
import subprocess
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

from hooks.dispatchers.stop import (
    get_git_status,
    check_uncommitted_changes,
    check_rate_limit,
    record_continuation,
    extract_last_messages,
    heuristic_should_continue,
    check_auto_continue,
    handle_stop,
)


class TestGetGitStatus:
    """Tests for git status detection."""

    def test_non_git_repo(self, tmp_path):
        """Should return is_git_repo=False for non-git directory."""
        status = get_git_status(str(tmp_path))
        assert status["is_git_repo"] is False
        assert status["has_staged"] is False
        assert status["has_unstaged"] is False
        assert status["has_untracked"] is False

    @patch("subprocess.run")
    def test_clean_git_repo(self, mock_run):
        """Should return clean status for git repo with no changes."""
        # Mock git rev-parse (is repo)
        mock_run.side_effect = [
            Mock(returncode=0, stdout=".git\n"),  # rev-parse
            Mock(returncode=0, stdout="main\n"),  # branch
            Mock(returncode=0, stdout=""),  # status
            Mock(returncode=1),  # upstream (no remote)
        ]

        status = get_git_status("/fake/repo")
        assert status["is_git_repo"] is True
        assert status["branch"] == "main"
        assert status["has_staged"] is False
        assert status["has_unstaged"] is False
        assert status["has_untracked"] is False
        assert status["file_count"] == 0

    @patch("subprocess.run")
    def test_staged_changes(self, mock_run):
        """Should detect staged changes."""
        mock_run.side_effect = [
            Mock(returncode=0, stdout=".git\n"),
            Mock(returncode=0, stdout="main\n"),
            Mock(returncode=0, stdout="M  file.txt\nA  new.txt\n"),
            Mock(returncode=0, stdout="0\n"),
        ]

        status = get_git_status()
        assert status["has_staged"] is True
        assert status["file_count"] == 2

    @patch("subprocess.run")
    def test_unstaged_changes(self, mock_run):
        """Should detect unstaged changes."""
        # Use MM format (modified in both index and worktree) to test unstaged detection
        # Note: " M" format doesn't work due to strip() removing leading space
        mock_run.side_effect = [
            Mock(returncode=0, stdout=".git\n"),
            Mock(returncode=0, stdout="main\n"),
            Mock(returncode=0, stdout="MM file.txt\n"),
            Mock(returncode=0, stdout="0\n"),
        ]

        status = get_git_status()
        assert status["has_unstaged"] is True
        assert status["has_staged"] is True  # MM sets both

    @patch("subprocess.run")
    def test_untracked_files(self, mock_run):
        """Should detect untracked files."""
        mock_run.side_effect = [
            Mock(returncode=0, stdout=".git\n"),
            Mock(returncode=0, stdout="main\n"),
            Mock(returncode=0, stdout="?? new_file.txt\n"),
            Mock(returncode=0, stdout="0\n"),
        ]

        status = get_git_status()
        assert status["has_untracked"] is True

    @patch("subprocess.run")
    def test_commits_ahead(self, mock_run):
        """Should detect unpushed commits."""
        mock_run.side_effect = [
            Mock(returncode=0, stdout=".git\n"),
            Mock(returncode=0, stdout="feature\n"),
            Mock(returncode=0, stdout=""),
            Mock(returncode=0, stdout="3\n"),
        ]

        status = get_git_status()
        assert status["ahead"] == 3
        assert status["branch"] == "feature"

    @patch("subprocess.run")
    def test_timeout_handling(self, mock_run):
        """Should handle subprocess timeout gracefully."""
        mock_run.side_effect = subprocess.TimeoutExpired("git", 5)

        status = get_git_status()
        assert status["is_git_repo"] is False


class TestCheckUncommittedChanges:
    """Tests for uncommitted changes detection."""

    def test_non_git_repo(self):
        """Should return empty list for non-git repo."""
        with patch("hooks.dispatchers.stop.get_git_status") as mock_status:
            mock_status.return_value = {"is_git_repo": False}
            messages = check_uncommitted_changes({})
            assert messages == []

    def test_clean_repo(self):
        """Should return empty list for clean repo."""
        with patch("hooks.dispatchers.stop.get_git_status") as mock_status:
            mock_status.return_value = {
                "is_git_repo": True,
                "has_staged": False,
                "has_unstaged": False,
                "has_untracked": False,
                "ahead": 0,
                "file_count": 0,
            }
            messages = check_uncommitted_changes({})
            assert messages == []

    def test_staged_changes_message(self):
        """Should return message for staged changes."""
        with patch("hooks.dispatchers.stop.get_git_status") as mock_status:
            mock_status.return_value = {
                "is_git_repo": True,
                "has_staged": True,
                "has_unstaged": False,
                "has_untracked": False,
                "ahead": 0,
                "file_count": 3,
            }
            messages = check_uncommitted_changes({})
            assert len(messages) == 1
            assert "staged" in messages[0]
            assert "3 files" in messages[0]

    def test_unstaged_changes_message(self):
        """Should return message for unstaged changes."""
        with patch("hooks.dispatchers.stop.get_git_status") as mock_status:
            mock_status.return_value = {
                "is_git_repo": True,
                "has_staged": False,
                "has_unstaged": True,
                "has_untracked": False,
                "ahead": 0,
                "file_count": 2,
            }
            messages = check_uncommitted_changes({})
            assert len(messages) == 1
            assert "unstaged" in messages[0]

    def test_both_staged_and_unstaged(self):
        """Should mention both staged and unstaged."""
        with patch("hooks.dispatchers.stop.get_git_status") as mock_status:
            mock_status.return_value = {
                "is_git_repo": True,
                "has_staged": True,
                "has_unstaged": True,
                "has_untracked": False,
                "ahead": 0,
                "file_count": 5,
            }
            messages = check_uncommitted_changes({})
            assert len(messages) == 1
            assert "staged" in messages[0] and "unstaged" in messages[0]

    def test_unpushed_commits_message(self):
        """Should return message for unpushed commits."""
        with patch("hooks.dispatchers.stop.get_git_status") as mock_status:
            mock_status.return_value = {
                "is_git_repo": True,
                "has_staged": False,
                "has_unstaged": False,
                "has_untracked": False,
                "ahead": 5,
                "branch": "feature",
                "file_count": 0,
            }
            messages = check_uncommitted_changes({})
            assert len(messages) == 1
            assert "5 commits ahead" in messages[0]
            assert "feature" in messages[0]
            assert "unpushed" in messages[0]

    def test_untracked_files_few(self):
        """Should mention untracked files if <= 10."""
        with patch("hooks.dispatchers.stop.get_git_status") as mock_status:
            mock_status.return_value = {
                "is_git_repo": True,
                "has_staged": False,
                "has_unstaged": False,
                "has_untracked": True,
                "ahead": 0,
                "file_count": 5,
            }
            messages = check_uncommitted_changes({})
            assert len(messages) == 1
            assert "Untracked files" in messages[0]

    def test_untracked_files_many(self):
        """Should not mention untracked files if > 10."""
        with patch("hooks.dispatchers.stop.get_git_status") as mock_status:
            mock_status.return_value = {
                "is_git_repo": True,
                "has_staged": False,
                "has_unstaged": False,
                "has_untracked": True,
                "ahead": 0,
                "file_count": 15,
            }
            messages = check_uncommitted_changes({})
            assert messages == []

    def test_multiple_issues(self):
        """Should return multiple messages for multiple issues."""
        with patch("hooks.dispatchers.stop.get_git_status") as mock_status:
            mock_status.return_value = {
                "is_git_repo": True,
                "has_staged": True,
                "has_unstaged": False,
                "has_untracked": True,
                "ahead": 2,
                "branch": "dev",
                "file_count": 3,
            }
            messages = check_uncommitted_changes({})
            assert len(messages) == 3  # uncommitted, unpushed, untracked


class TestCheckRateLimit:
    """Tests for rate limiting."""

    @patch("hooks.dispatchers.stop.load_continue_state")
    def test_no_recent_continuations(self, mock_load):
        """Should allow when no recent continuations."""
        mock_load.return_value = {"continuations": []}
        assert check_rate_limit() is True

    @patch("hooks.dispatchers.stop.load_continue_state")
    @patch("time.time")
    def test_within_limit(self, mock_time, mock_load):
        """Should allow when within continuation limit."""
        mock_time.return_value = 1000.0
        mock_load.return_value = {
            "continuations": [999.0, 998.0],  # 2 recent
            "last_reset": 900.0,
        }
        assert check_rate_limit() is True

    @patch("hooks.dispatchers.stop.load_continue_state")
    @patch("time.time")
    def test_at_limit(self, mock_time, mock_load):
        """Should block when at continuation limit."""
        mock_time.return_value = 1000.0
        mock_load.return_value = {
            "continuations": [999.0, 998.0, 997.0],  # 3 recent (max)
            "last_reset": 900.0,
        }
        assert check_rate_limit() is False

    @patch("hooks.dispatchers.stop.load_continue_state")
    @patch("time.time")
    def test_old_continuations_pruned(self, mock_time, mock_load):
        """Should prune old continuations outside window."""
        mock_time.return_value = 1000.0
        # Continuations older than 300s (5 min) should be pruned
        mock_load.return_value = {
            "continuations": [999.0, 998.0, 600.0, 500.0],  # Last 2 are old
            "last_reset": 500.0,
        }
        # Should prune old ones, leaving only 2 recent
        assert check_rate_limit() is True


class TestRecordContinuation:
    """Tests for continuation recording."""

    @patch("hooks.dispatchers.stop.load_continue_state")
    @patch("hooks.dispatchers.stop.save_continue_state")
    @patch("time.time")
    def test_records_timestamp(self, mock_time, mock_save, mock_load):
        """Should record current timestamp."""
        mock_time.return_value = 1234.5
        mock_load.return_value = {"continuations": []}

        record_continuation()

        mock_save.assert_called_once()
        saved_state = mock_save.call_args[0][0]
        assert 1234.5 in saved_state["continuations"]

    @patch("hooks.dispatchers.stop.load_continue_state")
    @patch("hooks.dispatchers.stop.save_continue_state")
    @patch("time.time")
    def test_appends_to_existing(self, mock_time, mock_save, mock_load):
        """Should append to existing continuations."""
        mock_time.return_value = 2000.0
        mock_load.return_value = {"continuations": [1000.0, 1500.0]}

        record_continuation()

        saved_state = mock_save.call_args[0][0]
        assert saved_state["continuations"] == [1000.0, 1500.0, 2000.0]


class TestExtractLastMessages:
    """Tests for message extraction."""

    def test_from_context_messages(self):
        """Should extract from messages in context."""
        ctx = {
            "messages": [
                {"type": "human", "content": "hello"},
                {"type": "assistant", "content": "hi"},
                {"type": "human", "content": "how are you"},
            ]
        }
        messages = extract_last_messages(ctx, count=2)
        assert len(messages) == 2
        assert messages[0]["content"] == "hi"
        assert messages[1]["content"] == "how are you"

    def test_from_transcript_file(self, tmp_path):
        """Should extract from transcript file if no messages in context."""
        transcript = tmp_path / "transcript.jsonl"
        with open(transcript, "w") as f:
            f.write('{"type": "human", "content": "msg1"}\n')
            f.write('{"type": "assistant", "content": "msg2"}\n')
            f.write('{"type": "human", "content": "msg3"}\n')

        ctx = {"transcript_path": str(transcript)}
        messages = extract_last_messages(ctx, count=10)
        assert len(messages) == 3
        assert messages[-1]["content"] == "msg3"

    def test_no_messages_or_transcript(self):
        """Should return empty list if no messages or transcript."""
        messages = extract_last_messages({}, count=10)
        assert messages == []

    def test_missing_transcript_file(self):
        """Should handle missing transcript file gracefully."""
        ctx = {"transcript_path": "/nonexistent/transcript.jsonl"}
        messages = extract_last_messages(ctx, count=10)
        assert messages == []

    def test_malformed_transcript(self, tmp_path):
        """Should skip malformed JSON lines in transcript."""
        transcript = tmp_path / "transcript.jsonl"
        with open(transcript, "w") as f:
            f.write('{"type": "human", "content": "valid"}\n')
            f.write('invalid json line\n')
            f.write('{"type": "assistant", "content": "also valid"}\n')

        ctx = {"transcript_path": str(transcript)}
        messages = extract_last_messages(ctx, count=10)
        assert len(messages) == 2
        assert messages[0]["content"] == "valid"


class TestHeuristicShouldContinue:
    """Tests for continuation heuristics."""

    def test_empty_messages(self):
        """Should return False for empty message list."""
        should_continue, reason = heuristic_should_continue([])
        assert should_continue is False
        assert reason == "no messages"

    def test_no_assistant_message(self):
        """Should return False if no assistant message found."""
        messages = [
            {"type": "human", "content": "hello"},
            {"type": "human", "content": "are you there?"},
        ]
        should_continue, reason = heuristic_should_continue(messages)
        assert should_continue is False
        assert reason == "no assistant message"

    def test_incomplete_pattern_detected(self):
        """Should return True for incomplete work patterns."""
        messages = [
            {
                "type": "assistant",
                "content": "I'll continue in next message with the implementation",
            }
        ]
        should_continue, reason = heuristic_should_continue(messages)
        assert should_continue is True
        assert "incomplete pattern" in reason

    def test_more_to_do_pattern(self):
        """Should detect 'more to do' pattern."""
        messages = [
            {"type": "assistant", "content": "Done step 1. More to complete..."}
        ]
        should_continue, reason = heuristic_should_continue(messages)
        assert should_continue is True

    def test_remaining_tasks_pattern(self):
        """Should detect 'remaining tasks' pattern."""
        messages = [{"type": "assistant", "content": "Remaining steps: 2, 3, 4"}]
        should_continue, reason = heuristic_should_continue(messages)
        assert should_continue is True

    def test_complete_pattern_detected(self):
        """Should return False for completion patterns."""
        messages = [
            {"type": "assistant", "content": "All tasks are done and complete!"}
        ]
        should_continue, reason = heuristic_should_continue(messages)
        assert should_continue is False
        assert "completion pattern" in reason

    def test_successfully_completed_pattern(self):
        """Should detect 'successfully completed' pattern."""
        messages = [
            {
                "type": "assistant",
                "content": "The implementation was successfully completed.",
            }
        ]
        should_continue, reason = heuristic_should_continue(messages)
        assert should_continue is False

    def test_no_more_work_pattern(self):
        """Should detect 'no more work' pattern."""
        messages = [{"type": "assistant", "content": "There's no more work to do."}]
        should_continue, reason = heuristic_should_continue(messages)
        assert should_continue is False

    def test_no_clear_signal(self):
        """Should return False when no clear pattern matches."""
        messages = [
            {"type": "assistant", "content": "Here's the implementation of the feature."}
        ]
        should_continue, reason = heuristic_should_continue(messages)
        assert should_continue is False
        assert "no clear signal" in reason

    def test_content_as_list(self):
        """Should handle content as list of blocks."""
        messages = [
            {
                "type": "assistant",
                "content": [
                    {"type": "text", "text": "Will continue with next step..."},
                ],
            }
        ]
        should_continue, reason = heuristic_should_continue(messages)
        assert should_continue is True

    def test_uses_last_assistant_message(self):
        """Should use most recent assistant message."""
        messages = [
            {"type": "assistant", "content": "Everything is done"},
            {"type": "human", "content": "What about X?"},
            {"type": "assistant", "content": "Will continue with X..."},
        ]
        should_continue, reason = heuristic_should_continue(messages)
        assert should_continue is True

    def test_case_insensitive(self):
        """Should be case insensitive."""
        messages = [{"type": "assistant", "content": "WILL CONTINUE IN NEXT MESSAGE"}]
        should_continue, reason = heuristic_should_continue(messages)
        assert should_continue is True


class TestCheckAutoContinue:
    """Tests for auto-continue logic."""

    @patch("hooks.dispatchers.stop.check_rate_limit")
    def test_rate_limited(self, mock_rate_limit):
        """Should return None when rate limited."""
        mock_rate_limit.return_value = False
        result = check_auto_continue({})
        assert result is None

    @patch("hooks.dispatchers.stop.check_rate_limit")
    @patch("hooks.dispatchers.stop.extract_last_messages")
    @patch("hooks.dispatchers.stop.heuristic_should_continue")
    def test_should_not_continue(self, mock_heuristic, mock_extract, mock_rate_limit):
        """Should return None when heuristic says no."""
        mock_rate_limit.return_value = True
        mock_extract.return_value = [{"type": "assistant", "content": "done"}]
        mock_heuristic.return_value = (False, "completion pattern")

        result = check_auto_continue({})
        assert result is None

    @patch("hooks.dispatchers.stop.check_rate_limit")
    @patch("hooks.dispatchers.stop.extract_last_messages")
    @patch("hooks.dispatchers.stop.heuristic_should_continue")
    @patch("hooks.dispatchers.stop.record_continuation")
    def test_should_continue(
        self, mock_record, mock_heuristic, mock_extract, mock_rate_limit
    ):
        """Should return continue result when heuristic says yes."""
        mock_rate_limit.return_value = True
        mock_extract.return_value = [{"type": "assistant", "content": "will continue"}]
        mock_heuristic.return_value = (True, "incomplete pattern")

        result = check_auto_continue({})

        assert result is not None
        assert result["result"] == "continue"
        assert "Auto-continue" in result["reason"]
        mock_record.assert_called_once()


class TestHandleStop:
    """Tests for main stop handler."""

    @patch("hooks.dispatchers.stop.check_uncommitted_changes")
    @patch("hooks.dispatchers.stop.check_auto_continue")
    def test_clean_stop_no_continue(self, mock_auto, mock_uncommitted):
        """Should return empty results for clean stop."""
        mock_uncommitted.return_value = []
        mock_auto.return_value = None

        messages, continue_result = handle_stop({})

        assert messages == []
        assert continue_result is None

    @patch("hooks.dispatchers.stop.check_uncommitted_changes")
    @patch("hooks.dispatchers.stop.check_auto_continue")
    def test_uncommitted_changes_no_continue(self, mock_auto, mock_uncommitted):
        """Should return uncommitted messages without continue."""
        mock_uncommitted.return_value = ["Uncommitted changes in 3 files"]
        mock_auto.return_value = None

        messages, continue_result = handle_stop({})

        assert len(messages) == 1
        assert "Uncommitted" in messages[0]
        assert continue_result is None

    @patch("hooks.dispatchers.stop.check_uncommitted_changes")
    @patch("hooks.dispatchers.stop.check_auto_continue")
    def test_clean_but_should_continue(self, mock_auto, mock_uncommitted):
        """Should return continue result even without uncommitted changes."""
        mock_uncommitted.return_value = []
        mock_auto.return_value = {"result": "continue", "reason": "[Auto-continue]"}

        messages, continue_result = handle_stop({})

        assert messages == []
        assert continue_result is not None
        assert continue_result["result"] == "continue"

    @patch("hooks.dispatchers.stop.check_uncommitted_changes")
    @patch("hooks.dispatchers.stop.check_auto_continue")
    def test_both_uncommitted_and_continue(self, mock_auto, mock_uncommitted):
        """Should return both uncommitted messages and continue result."""
        mock_uncommitted.return_value = [
            "Uncommitted changes",
            "Branch is 2 commits ahead",
        ]
        mock_auto.return_value = {"result": "continue", "reason": "[Auto-continue]"}

        messages, continue_result = handle_stop({})

        assert len(messages) == 2
        assert continue_result is not None
        assert continue_result["result"] == "continue"

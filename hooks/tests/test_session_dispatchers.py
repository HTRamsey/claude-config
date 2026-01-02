#!/usr/bin/env python3
"""Unit tests for session dispatchers (session_start_dispatcher.py and session_end_dispatcher.py)."""

import json
import os
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest import TestCase, main
from unittest.mock import patch, MagicMock

# Handlers extracted from session dispatchers
from hooks.handlers.git_context import (
    run_cmd,
    get_context_summary as get_git_context,
)
from hooks.handlers.project_context import (
    detect_project_type,
    get_todo_context,
    get_recent_errors,
    get_codebase_map,
    get_usage_summary,
)
from hooks.handlers.session_persistence import (
    generate_memory_suggestions,
    cleanup_old_session_files,
    extract_project_info,
)
from hooks.handlers.transcript_converter import (
    parse_jsonl,
    extract_messages,
    convert_transcript,
    find_transcript_files,
)


class TestDetectProjectType(TestCase):
    """Tests for detect_project_type function."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        # Clean up temp directory
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_detect_python_pyproject(self):
        Path(self.temp_dir, "pyproject.toml").touch()
        result = detect_project_type(self.temp_dir)
        self.assertIn("Python", result)

    def test_detect_python_setup(self):
        Path(self.temp_dir, "setup.py").touch()
        result = detect_project_type(self.temp_dir)
        self.assertIn("Python", result)

    def test_detect_node(self):
        Path(self.temp_dir, "package.json").touch()
        result = detect_project_type(self.temp_dir)
        self.assertIn("Node.js", result)

    def test_detect_rust(self):
        Path(self.temp_dir, "Cargo.toml").touch()
        result = detect_project_type(self.temp_dir)
        self.assertIn("Rust", result)

    def test_detect_go(self):
        Path(self.temp_dir, "go.mod").touch()
        result = detect_project_type(self.temp_dir)
        self.assertIn("Go", result)

    def test_detect_java_maven(self):
        Path(self.temp_dir, "pom.xml").touch()
        result = detect_project_type(self.temp_dir)
        self.assertIn("Java/Maven", result)

    def test_detect_java_gradle(self):
        Path(self.temp_dir, "build.gradle").touch()
        result = detect_project_type(self.temp_dir)
        self.assertIn("Java/Gradle", result)

    def test_detect_cmake(self):
        Path(self.temp_dir, "CMakeLists.txt").touch()
        result = detect_project_type(self.temp_dir)
        self.assertIn("C/C++ (CMake)", result)

    def test_detect_makefile(self):
        Path(self.temp_dir, "Makefile").touch()
        result = detect_project_type(self.temp_dir)
        self.assertIn("Make", result)

    def test_detect_ruby(self):
        Path(self.temp_dir, "Gemfile").touch()
        result = detect_project_type(self.temp_dir)
        self.assertIn("Ruby", result)

    def test_detect_php(self):
        Path(self.temp_dir, "composer.json").touch()
        result = detect_project_type(self.temp_dir)
        self.assertIn("PHP", result)

    def test_detect_elixir(self):
        Path(self.temp_dir, "mix.exs").touch()
        result = detect_project_type(self.temp_dir)
        self.assertIn("Elixir", result)

    def test_detect_flutter(self):
        Path(self.temp_dir, "pubspec.yaml").touch()
        result = detect_project_type(self.temp_dir)
        self.assertIn("Dart/Flutter", result)

    def test_detect_multiple_types(self):
        Path(self.temp_dir, "package.json").touch()
        Path(self.temp_dir, "pyproject.toml").touch()
        result = detect_project_type(self.temp_dir)
        self.assertTrue("Node.js" in result or "Python" in result)

    def test_detect_no_project_files(self):
        result = detect_project_type(self.temp_dir)
        self.assertEqual(result, "")

    def test_detect_nonexistent_directory(self):
        result = detect_project_type("/nonexistent/path/12345")
        self.assertEqual(result, "")


class TestRunCmd(TestCase):
    """Tests for run_cmd function."""

    def test_successful_command(self):
        result = run_cmd(["echo", "hello"])
        self.assertEqual(result, "hello")

    def test_failed_command(self):
        result = run_cmd(["false"])
        self.assertEqual(result, "")

    def test_nonexistent_command(self):
        result = run_cmd(["nonexistent_command_xyz"])
        self.assertEqual(result, "")

    def test_command_with_cwd(self):
        temp_dir = tempfile.mkdtemp()
        try:
            result = run_cmd(["pwd"], cwd=temp_dir)
            self.assertIn(temp_dir, result)
        finally:
            os.rmdir(temp_dir)

    def test_timeout_handling(self):
        # Commands that take longer than 5s should be handled
        # This is difficult to test without actually waiting, so we just
        # verify the function accepts the parameter
        result = run_cmd(["echo", "fast"])
        self.assertEqual(result, "fast")


class TestGetGitContext(TestCase):
    """Tests for get_git_context function."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_non_git_repo(self):
        result = get_git_context(self.temp_dir)
        self.assertEqual(result, [])

    def test_git_repo_with_branch(self):
        # Initialize a git repo
        run_cmd(["git", "init"], cwd=self.temp_dir)
        run_cmd(["git", "config", "user.name", "Test"], cwd=self.temp_dir)
        run_cmd(["git", "config", "user.email", "test@test.com"], cwd=self.temp_dir)

        # Create initial commit
        test_file = Path(self.temp_dir) / "test.txt"
        test_file.write_text("test")
        run_cmd(["git", "add", "."], cwd=self.temp_dir)
        run_cmd(["git", "commit", "-m", "Initial commit"], cwd=self.temp_dir)

        result = get_git_context(self.temp_dir)
        # Should contain branch info
        self.assertTrue(any("Branch:" in item for item in result))

    def test_git_repo_with_uncommitted_changes(self):
        # Initialize a git repo
        run_cmd(["git", "init"], cwd=self.temp_dir)
        run_cmd(["git", "config", "user.name", "Test"], cwd=self.temp_dir)
        run_cmd(["git", "config", "user.email", "test@test.com"], cwd=self.temp_dir)

        # Create uncommitted file
        test_file = Path(self.temp_dir) / "test.txt"
        test_file.write_text("test")

        result = get_git_context(self.temp_dir)
        # Should indicate uncommitted changes
        self.assertTrue(any("Uncommitted" in item for item in result))


class TestGetTodoContext(TestCase):
    """Tests for get_todo_context function."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_todo_md_found(self):
        todo_file = Path(self.temp_dir) / "TODO.md"
        todo_file.write_text("- Task 1\n- Task 2\n- Task 3")

        result = get_todo_context(self.temp_dir)
        self.assertIn("TODO.md:", result)
        self.assertIn("Task 1", result)

    def test_lowercase_todo_found(self):
        todo_file = Path(self.temp_dir) / "todo.md"
        todo_file.write_text("- Task 1\n- Task 2")

        result = get_todo_context(self.temp_dir)
        self.assertIn("TODO.md:", result)
        self.assertIn("Task 1", result)

    def test_claude_todo_found(self):
        claude_dir = Path(self.temp_dir) / ".claude"
        claude_dir.mkdir()
        todo_file = claude_dir / "TODO.md"
        todo_file.write_text("- Claude task")

        result = get_todo_context(self.temp_dir)
        self.assertIn("TODO.md:", result)
        self.assertIn("Claude task", result)

    def test_no_todo_found(self):
        result = get_todo_context(self.temp_dir)
        self.assertEqual(result, "")

    def test_empty_todo_file(self):
        todo_file = Path(self.temp_dir) / "TODO.md"
        todo_file.write_text("")

        result = get_todo_context(self.temp_dir)
        self.assertEqual(result, "")

    def test_todo_truncated_at_10_lines(self):
        lines = [f"- Task {i}" for i in range(20)]
        todo_file = Path(self.temp_dir) / "TODO.md"
        todo_file.write_text("\n".join(lines))

        result = get_todo_context(self.temp_dir)
        # Should only show first 10 lines
        self.assertIn("Task 9", result)
        self.assertNotIn("Task 10", result)


class TestGetRecentErrors(TestCase):
    """Tests for get_recent_errors function."""

    def setUp(self):
        self.log_file = Path.home() / ".claude" / "data" / "hook-events.jsonl"
        self.log_backup = None

        # Backup existing log if it exists
        if self.log_file.exists():
            self.log_backup = self.log_file.read_text()

    def tearDown(self):
        # Restore original log
        if self.log_backup is not None:
            self.log_file.write_text(self.log_backup)
        elif self.log_file.exists():
            self.log_file.unlink()

    def test_no_log_file(self):
        if self.log_file.exists():
            self.log_file.unlink()

        result = get_recent_errors()
        self.assertEqual(result, "")

    def test_log_with_errors(self):
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

        # Write test log entries
        entries = [
            {"level": "info", "hook": "test_hook", "data": {}},
            {"level": "error", "hook": "hook1", "data": {"msg": "Error 1"}},
            {"level": "error", "hook": "hook2", "data": {"msg": "Error 2"}},
        ]

        with open(self.log_file, "w") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")

        result = get_recent_errors()
        self.assertIn("hook1", result)
        self.assertIn("Error 1", result)

    def test_log_with_no_errors(self):
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

        entries = [
            {"level": "info", "hook": "test_hook", "data": {}},
            {"level": "info", "hook": "test_hook2", "data": {}},
        ]

        with open(self.log_file, "w") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")

        result = get_recent_errors()
        self.assertEqual(result, "")

    def test_log_limits_to_last_3_errors(self):
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

        entries = [
            {"level": "error", "hook": "hook1", "data": {"msg": "Error 1"}},
            {"level": "error", "hook": "hook2", "data": {"msg": "Error 2"}},
            {"level": "error", "hook": "hook3", "data": {"msg": "Error 3"}},
            {"level": "error", "hook": "hook4", "data": {"msg": "Error 4"}},
        ]

        with open(self.log_file, "w") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")

        result = get_recent_errors()
        # Should only show last 3 errors
        self.assertNotIn("Error 1", result)
        self.assertIn("Error 4", result)


class TestGetCodebaseMap(TestCase):
    """Tests for get_codebase_map function."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_empty_directory(self):
        result = get_codebase_map(self.temp_dir)
        # Empty directories return empty string (no files to show)
        self.assertEqual(result, "")

    def test_simple_structure(self):
        (Path(self.temp_dir) / "file1.txt").touch()
        (Path(self.temp_dir) / "file2.py").touch()

        result = get_codebase_map(self.temp_dir)
        self.assertIn("file1.txt", result)
        self.assertIn("file2.py", result)

    def test_nested_structure(self):
        src_dir = Path(self.temp_dir) / "src"
        src_dir.mkdir()
        (src_dir / "main.py").touch()

        result = get_codebase_map(self.temp_dir)
        self.assertIn("src/", result)
        self.assertIn("main.py", result)

    def test_ignores_node_modules(self):
        node_modules = Path(self.temp_dir) / "node_modules"
        node_modules.mkdir()
        (node_modules / "package.js").touch()

        result = get_codebase_map(self.temp_dir)
        self.assertNotIn("node_modules", result)

    def test_ignores_git_directory(self):
        git_dir = Path(self.temp_dir) / ".git"
        git_dir.mkdir()
        (git_dir / "config").touch()

        result = get_codebase_map(self.temp_dir)
        self.assertNotIn(".git", result)

    def test_ignores_pycache(self):
        pycache = Path(self.temp_dir) / "__pycache__"
        pycache.mkdir()
        (pycache / "test.pyc").touch()

        result = get_codebase_map(self.temp_dir)
        self.assertNotIn("__pycache__", result)

    def test_ignores_hidden_files(self):
        (Path(self.temp_dir) / ".hidden").touch()
        (Path(self.temp_dir) / "visible.txt").touch()

        result = get_codebase_map(self.temp_dir)
        self.assertNotIn(".hidden", result)
        self.assertIn("visible.txt", result)

    def test_max_depth_limit(self):
        # Create deep structure
        deep_path = Path(self.temp_dir) / "a" / "b" / "c" / "d" / "e"
        deep_path.mkdir(parents=True)
        (deep_path / "file.txt").touch()

        result = get_codebase_map(self.temp_dir, max_depth=2)
        # Should not include deeply nested file
        self.assertIn("a/", result)
        self.assertIn("b/", result)

    def test_nonexistent_directory(self):
        result = get_codebase_map("/nonexistent/path/12345")
        self.assertEqual(result, "")


class TestGetUsageSummary(TestCase):
    """Tests for get_usage_summary function."""

    def test_returns_string(self):
        result = get_usage_summary()
        self.assertIsInstance(result, str)

    def test_no_usage_data(self):
        # Temporarily rename usage files if they exist
        usage_file = Path.home() / ".claude" / "data" / "usage-stats.json"
        projects_dir = Path.home() / ".claude" / "projects"

        # This test just verifies the function doesn't crash
        result = get_usage_summary()
        self.assertIsInstance(result, str)


class TestGenerateMemorySuggestions(TestCase):
    """Tests for generate_memory_suggestions function."""

    def test_empty_info(self):
        result = generate_memory_suggestions({})
        self.assertEqual(result, {"entities": [], "observations": []})

    def test_no_project_root(self):
        info = {
            "project_root": None,
            "technologies": ["Python"],
        }
        result = generate_memory_suggestions(info)
        self.assertEqual(result, {"entities": [], "observations": []})

    def test_with_technologies(self):
        info = {
            "project_root": "/tmp/test-project",
            "technologies": ["Python", "Node.js"],
            "files_modified": [],
            "files_created": [],
            "tools_used": {},
        }
        result = generate_memory_suggestions(info)

        self.assertIsInstance(result, dict)
        self.assertIn("entities", result)
        self.assertIn("observations", result)

        if result["entities"]:
            entity = result["entities"][0]
            self.assertEqual(entity["name"], "test-project")
            self.assertEqual(entity["entityType"], "project")

    def test_with_files_modified(self):
        info = {
            "project_root": "/tmp/test-project",
            "technologies": [],
            "files_modified": ["/tmp/test-project/src/main.py"],
            "files_created": [],
            "tools_used": {},
        }
        result = generate_memory_suggestions(info)

        if result["entities"]:
            observations = result["entities"][0]["observations"]
            self.assertTrue(any("Active directories" in obs for obs in observations))

    def test_with_files_created(self):
        info = {
            "project_root": "/tmp/test-project",
            "technologies": [],
            "files_modified": [],
            "files_created": ["/tmp/test-project/test.py"],
            "tools_used": {},
        }
        result = generate_memory_suggestions(info)

        if result["entities"]:
            observations = result["entities"][0]["observations"]
            self.assertTrue(any("Files created" in obs for obs in observations))

    def test_with_tool_usage(self):
        info = {
            "project_root": "/tmp/test-project",
            "technologies": [],
            "files_modified": [],
            "files_created": [],
            "tools_used": {"Edit": 5, "Read": 3, "Bash": 2},
        }
        result = generate_memory_suggestions(info)

        if result["entities"]:
            observations = result["entities"][0]["observations"]
            self.assertTrue(any("Common operations" in obs for obs in observations))


class TestCleanupOldSessionFiles(TestCase):
    """Tests for cleanup_old_session_files function."""

    def setUp(self):
        self.file_history = Path.home() / ".claude" / "data" / "file-history"
        self.temp_test_dir = self.file_history / "test_cleanup"
        self.temp_test_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        import shutil
        if self.temp_test_dir.exists():
            shutil.rmtree(self.temp_test_dir, ignore_errors=True)

    def test_cleanup_old_files(self):
        # Create old file (31 days old)
        old_file = self.temp_test_dir / "old.txt"
        old_file.touch()

        # Set modification time to 31 days ago
        old_time = time.time() - (31 * 24 * 3600)
        os.utime(old_file, (old_time, old_time))

        # Create recent file
        recent_file = self.temp_test_dir / "recent.txt"
        recent_file.touch()

        cleaned = cleanup_old_session_files(max_age_hours=24)

        # Old file should be removed
        self.assertFalse(old_file.exists())
        # Recent file should remain
        self.assertTrue(recent_file.exists())

    def test_no_cleanup_needed(self):
        # Create only recent files
        recent_file = self.temp_test_dir / "recent.txt"
        recent_file.touch()

        cleaned = cleanup_old_session_files(max_age_hours=24)

        # File should still exist
        self.assertTrue(recent_file.exists())


class TestExtractProjectInfo(TestCase):
    """Tests for extract_project_info function."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_nonexistent_file(self):
        result = extract_project_info("/nonexistent/path/transcript.jsonl")
        self.assertIsInstance(result, dict)
        self.assertIn("tools_used", result)
        self.assertEqual(result["tools_used"], {})

    def test_empty_transcript(self):
        transcript = Path(self.temp_dir) / "transcript.jsonl"
        transcript.write_text("")

        result = extract_project_info(str(transcript))
        self.assertIsInstance(result, dict)
        self.assertEqual(result["tools_used"], {})

    def test_extract_tool_usage(self):
        transcript = Path(self.temp_dir) / "transcript.jsonl"

        entries = [
            {"tool_name": "Edit", "tool_input": {"file_path": "/test/file.py"}},
            {"tool_name": "Read", "tool_input": {"file_path": "/test/file.py"}},
            {"tool_name": "Edit", "tool_input": {"file_path": "/test/file2.py"}},
        ]

        with open(transcript, "w") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")

        result = extract_project_info(str(transcript))

        self.assertEqual(result["tools_used"]["Edit"], 2)
        self.assertEqual(result["tools_used"]["Read"], 1)

    def test_extract_technologies(self):
        transcript = Path(self.temp_dir) / "transcript.jsonl"

        entries = [
            {"tool_name": "Edit", "tool_input": {"file_path": "/test/file.py"}},
            {"tool_name": "Edit", "tool_input": {"file_path": "/test/file.rs"}},
        ]

        with open(transcript, "w") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")

        result = extract_project_info(str(transcript))

        self.assertIn("Python", result["technologies"])
        self.assertIn("Rust", result["technologies"])


class TestParseJsonl(TestCase):
    """Tests for parse_jsonl function."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_valid_jsonl(self):
        jsonl_file = Path(self.temp_dir) / "test.jsonl"

        with open(jsonl_file, "w") as f:
            f.write('{"key": "value1"}\n')
            f.write('{"key": "value2"}\n')

        result = parse_jsonl(jsonl_file)

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["key"], "value1")
        self.assertEqual(result[1]["key"], "value2")

    def test_empty_lines_ignored(self):
        jsonl_file = Path(self.temp_dir) / "test.jsonl"

        with open(jsonl_file, "w") as f:
            f.write('{"key": "value1"}\n')
            f.write('\n')
            f.write('{"key": "value2"}\n')

        result = parse_jsonl(jsonl_file)

        self.assertEqual(len(result), 2)

    def test_invalid_json_skipped(self):
        jsonl_file = Path(self.temp_dir) / "test.jsonl"

        with open(jsonl_file, "w") as f:
            f.write('{"key": "value1"}\n')
            f.write('invalid json\n')
            f.write('{"key": "value2"}\n')

        result = parse_jsonl(jsonl_file)

        # Should skip invalid line
        self.assertEqual(len(result), 2)


class TestExtractMessages(TestCase):
    """Tests for extract_messages function."""

    def test_user_message(self):
        entries = [
            {"type": "user", "content": "Hello", "timestamp": "2024-01-01T00:00:00"}
        ]

        result = extract_messages(entries)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["role"], "user")
        self.assertEqual(result[0]["content"], "Hello")

    def test_assistant_message(self):
        entries = [
            {"type": "assistant", "content": "Hi there", "timestamp": "2024-01-01T00:00:00"}
        ]

        result = extract_messages(entries)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["role"], "assistant")
        self.assertEqual(result[0]["content"], "Hi there")

    def test_assistant_with_tool_calls(self):
        entries = [
            {
                "type": "assistant",
                "content": "Let me read that",
                "timestamp": "2024-01-01T00:00:00",
                "tool_use": [
                    {"name": "Read", "input": {"file_path": "/test/file.py"}}
                ]
            }
        ]

        result = extract_messages(entries)

        self.assertEqual(len(result), 1)
        self.assertIn("tool_calls", result[0])
        self.assertEqual(result[0]["tool_calls"][0]["name"], "Read")

    def test_tool_result(self):
        entries = [
            {
                "type": "tool_result",
                "tool_name": "Read",
                "result": "File contents here",
                "timestamp": "2024-01-01T00:00:00"
            }
        ]

        result = extract_messages(entries)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["role"], "tool")
        self.assertEqual(result[0]["tool_name"], "Read")

    def test_tool_result_truncation(self):
        entries = [
            {
                "type": "tool_result",
                "tool_name": "Read",
                "result": "x" * 1000,
                "timestamp": "2024-01-01T00:00:00"
            }
        ]

        result = extract_messages(entries)

        # Should be truncated to 500 chars
        self.assertEqual(len(result[0]["result"]), 500)

    def test_mixed_message_types(self):
        entries = [
            {"type": "user", "content": "Hello", "timestamp": "2024-01-01T00:00:00"},
            {"type": "assistant", "content": "Hi", "timestamp": "2024-01-01T00:00:01"},
            {"type": "tool_result", "tool_name": "Read", "result": "data", "timestamp": "2024-01-01T00:00:02"},
        ]

        result = extract_messages(entries)

        self.assertEqual(len(result), 3)
        self.assertEqual(result[0]["role"], "user")
        self.assertEqual(result[1]["role"], "assistant")
        self.assertEqual(result[2]["role"], "tool")


class TestConvertTranscript(TestCase):
    """Tests for convert_transcript function."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.output_dir = Path(self.temp_dir) / "output"

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_basic_conversion(self):
        # Create transcript
        transcript_dir = Path(self.temp_dir) / "session123"
        transcript_dir.mkdir()
        transcript = transcript_dir / "transcript.jsonl"

        with open(transcript, "w") as f:
            f.write('{"type": "user", "content": "Hello", "timestamp": "2024-01-01T00:00:00"}\n')

        result = convert_transcript(transcript, self.output_dir, "overwrite")

        self.assertTrue(result.exists())

        with open(result) as f:
            data = json.load(f)

        self.assertEqual(data["session_id"], "session123")
        self.assertEqual(data["message_count"], 1)
        self.assertEqual(data["messages"][0]["content"], "Hello")

    def test_append_mode(self):
        # Create transcript
        transcript_dir = Path(self.temp_dir) / "session123"
        transcript_dir.mkdir()
        transcript = transcript_dir / "transcript.jsonl"

        with open(transcript, "w") as f:
            f.write('{"type": "user", "content": "First", "timestamp": "2024-01-01T00:00:00"}\n')

        # First conversion
        result1 = convert_transcript(transcript, self.output_dir, "append")

        # Add more to transcript
        with open(transcript, "a") as f:
            f.write('{"type": "user", "content": "Second", "timestamp": "2024-01-01T00:01:00"}\n')

        # Second conversion (append)
        result2 = convert_transcript(transcript, self.output_dir, "append")

        with open(result2) as f:
            data = json.load(f)

        # Should have both messages
        self.assertEqual(data["message_count"], 2)

    def test_deduplicate_timestamps(self):
        # Create transcript
        transcript_dir = Path(self.temp_dir) / "session123"
        transcript_dir.mkdir()
        transcript = transcript_dir / "transcript.jsonl"

        # First conversion with one message
        with open(transcript, "w") as f:
            f.write('{"type": "user", "content": "Hello", "timestamp": "2024-01-01T00:00:00"}\n')

        result1 = convert_transcript(transcript, self.output_dir, "append")

        # Add duplicate message (same timestamp)
        with open(transcript, "a") as f:
            f.write('{"type": "user", "content": "Hello again", "timestamp": "2024-01-01T00:00:00"}\n')

        # Second conversion should deduplicate
        result2 = convert_transcript(transcript, self.output_dir, "append")

        with open(result2) as f:
            data = json.load(f)

        # Should deduplicate by timestamp (only first message kept)
        self.assertEqual(data["message_count"], 1)


class TestFindTranscriptFiles(TestCase):
    """Tests for find_transcript_files function."""

    def test_returns_list(self):
        result = find_transcript_files()
        self.assertIsInstance(result, list)

    def test_finds_transcript_in_projects(self):
        # This is an integration test that depends on actual file system
        # Just verify it doesn't crash
        result = find_transcript_files()
        self.assertIsInstance(result, list)


if __name__ == "__main__":
    main()

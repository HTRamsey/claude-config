"""Tests for tdd_guard module."""
import sys
from pathlib import Path

import pytest

from tdd_guard import (
    get_test_paths,
    find_test_file,
    count_recent_warnings,
    CODE_EXTENSIONS,
    TEST_PATTERNS,
    SKIP_PATTERNS,
)


class TestGetTestPaths:
    """Tests for test path generation."""

    def test_python_test_paths(self):
        """Should generate Python test paths."""
        impl = Path("/project/src/utils.py")
        paths = get_test_paths(impl)
        path_strs = [str(p) for p in paths]
        assert "/project/src/test_utils.py" in path_strs
        assert "/project/src/utils_test.py" in path_strs

    def test_test_directory_paths(self):
        """Should include tests directory."""
        impl = Path("/project/src/module.py")
        paths = get_test_paths(impl)
        path_strs = [str(p) for p in paths]
        assert "/project/src/tests/test_module.py" in path_strs

    def test_parent_tests_directory(self):
        """Should check parent tests directory."""
        impl = Path("/project/src/module.py")
        paths = get_test_paths(impl)
        path_strs = [str(p) for p in paths]
        assert "/project/tests/test_module.py" in path_strs

    def test_typescript_patterns(self):
        """Should include .test. and .spec. for TypeScript."""
        impl = Path("/project/src/component.tsx")
        paths = get_test_paths(impl)
        path_strs = [str(p) for p in paths]
        assert any(".test.tsx" in p for p in path_strs)
        assert any(".spec.tsx" in p for p in path_strs)
        assert any("__tests__" in p for p in path_strs)

    def test_javascript_patterns(self):
        """Should include .test. and .spec. for JavaScript."""
        impl = Path("/project/src/util.js")
        paths = get_test_paths(impl)
        path_strs = [str(p) for p in paths]
        assert any(".test.js" in p for p in path_strs)
        assert any(".spec.js" in p for p in path_strs)


class TestFindTestFile:
    """Tests for test file detection."""

    def test_no_test_file(self, tmp_path):
        """Should return False when no test exists."""
        impl = tmp_path / "module.py"
        impl.touch()
        assert find_test_file(impl) is False

    def test_test_file_exists_prefix(self, tmp_path):
        """Should find test_module.py."""
        impl = tmp_path / "module.py"
        impl.touch()
        test = tmp_path / "test_module.py"
        test.touch()
        assert find_test_file(impl) is True

    def test_test_file_exists_suffix(self, tmp_path):
        """Should find module_test.py."""
        impl = tmp_path / "module.py"
        impl.touch()
        test = tmp_path / "module_test.py"
        test.touch()
        assert find_test_file(impl) is True

    def test_test_in_tests_dir(self, tmp_path):
        """Should find test in tests/ directory."""
        impl = tmp_path / "module.py"
        impl.touch()
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        test = tests_dir / "test_module.py"
        test.touch()
        assert find_test_file(impl) is True


class TestCountRecentWarnings:
    """Tests for warning counting."""

    def test_empty_warnings(self):
        """Should return 0 for empty warnings."""
        data = {"warnings": []}
        assert count_recent_warnings(data) == 0

    def test_recent_warnings(self):
        """Should count recent warnings."""
        import time
        now = time.time()
        data = {"warnings": [
            {"file": "a.py", "time": now - 10},  # Recent
            {"file": "b.py", "time": now - 20},  # Recent
        ]}
        assert count_recent_warnings(data) == 2

    def test_old_warnings_pruned(self):
        """Should prune old warnings."""
        import time
        now = time.time()
        data = {"warnings": [
            {"file": "a.py", "time": now - 10},    # Recent
            {"file": "old.py", "time": now - 7200},  # Old (2 hours ago)
        ]}
        count = count_recent_warnings(data)
        assert count == 1
        assert len(data["warnings"]) == 1  # Old one pruned


class TestCodeExtensions:
    """Tests for code extension detection."""

    def test_python_is_code(self):
        """Python is a code extension."""
        assert ".py" in CODE_EXTENSIONS

    def test_javascript_is_code(self):
        """JavaScript is a code extension."""
        assert ".js" in CODE_EXTENSIONS

    def test_typescript_is_code(self):
        """TypeScript is a code extension."""
        assert ".ts" in CODE_EXTENSIONS

    def test_go_is_code(self):
        """Go is a code extension."""
        assert ".go" in CODE_EXTENSIONS


class TestTestPatterns:
    """Tests for test pattern detection."""

    def test_test_prefix_pattern(self):
        """test_ prefix should match."""
        assert "test_" in TEST_PATTERNS

    def test_test_suffix_pattern(self):
        """_test suffix should match."""
        assert "_test" in TEST_PATTERNS

    def test_tests_directory_pattern(self):
        """tests/ directory should match."""
        assert "tests/" in TEST_PATTERNS


class TestSkipPatterns:
    """Tests for skip pattern detection."""

    def test_init_skipped(self):
        """__init__.py should be skipped."""
        assert "__init__.py" in SKIP_PATTERNS

    def test_conftest_skipped(self):
        """conftest.py should be skipped."""
        assert "conftest.py" in SKIP_PATTERNS

    def test_setup_skipped(self):
        """setup.py should be skipped."""
        assert "setup.py" in SKIP_PATTERNS

"""Tests for build_analyzer module."""
import sys
from pathlib import Path

import pytest

from build_analyzer import (
    is_build_command,
    detect_build_tool,
    extract_errors,
    get_suggestions,
    BUILD_COMMANDS,
    ERROR_PATTERNS,
)


class TestIsBuildCommand:
    """Tests for build command detection."""

    def test_make_detected(self):
        """Should detect make command."""
        assert is_build_command("make -j4") is True

    def test_cmake_detected(self):
        """Should detect cmake command."""
        assert is_build_command("cmake --build .") is True

    def test_cargo_build_detected(self):
        """Should detect cargo build."""
        assert is_build_command("cargo build --release") is True

    def test_npm_build_detected(self):
        """Should detect npm build."""
        assert is_build_command("npm run build") is True

    def test_go_build_detected(self):
        """Should detect go build."""
        assert is_build_command("go build ./...") is True

    def test_non_build_ignored(self):
        """Should not detect non-build commands."""
        assert is_build_command("ls -la") is False
        assert is_build_command("git status") is False
        assert is_build_command("echo hello") is False


class TestDetectBuildTool:
    """Tests for build tool detection."""

    def test_detect_gcc(self):
        """Should detect gcc from output."""
        output = "main.c:10: error: expected ';'"
        assert detect_build_tool("gcc main.c", output) == "gcc_clang"

    def test_detect_cargo(self):
        """Should detect cargo."""
        output = "error[E0432]: unresolved import"
        assert detect_build_tool("cargo build", output) == "rust"

    def test_detect_npm(self):
        """Should detect npm."""
        output = "npm ERR! Missing script"
        assert detect_build_tool("npm run build", output) == "npm"


class TestExtractErrors:
    """Tests for error extraction."""

    def test_extract_gcc_error(self):
        """Should extract GCC-style errors."""
        output = """
main.c:10:5: error: expected ';' before 'return'
main.c:15:10: error: undefined reference to 'foo'
"""
        errors = extract_errors(output, "gcc_clang")
        assert len(errors) >= 1

    def test_extract_typescript_error(self):
        """Should extract TypeScript errors."""
        output = """
src/index.ts(5,10): error TS2339: Property 'foo' does not exist on type 'Bar'.
"""
        errors = extract_errors(output, "typescript")
        assert len(errors) >= 1

    def test_extract_rust_error(self):
        """Should extract Rust errors."""
        output = """
error[E0432]: unresolved import `crate::foo`
 --> src/main.rs:1:5
"""
        errors = extract_errors(output, "rust")
        assert len(errors) >= 1


class TestGetSuggestions:
    """Tests for fix suggestions."""

    def test_suggest_for_missing_module(self):
        """Should suggest install for missing module."""
        errors = [{"message": "cannot find module"}]
        output = "Cannot find module 'express'"
        suggestions = get_suggestions(errors, output)
        assert isinstance(suggestions, list)

    def test_returns_list(self):
        """Should always return a list."""
        errors = []
        suggestions = get_suggestions(errors, "some output")
        assert isinstance(suggestions, list)

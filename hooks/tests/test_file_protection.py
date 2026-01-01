"""Tests for file_protection module."""
import sys
from pathlib import Path

import pytest

from hooks.config import ProtectedFiles
from hooks.hook_sdk import Patterns, expand_path


class TestProtectedPatterns:
    """Tests for protected file patterns."""

    def test_env_files_protected(self):
        """Env files should be protected."""
        assert any(".env" in p for p in ProtectedFiles.PROTECTED_PATTERNS)

    def test_ssh_protected(self):
        """SSH directory should be protected."""
        assert any(".ssh" in p for p in ProtectedFiles.PROTECTED_PATTERNS)

    def test_aws_protected(self):
        """AWS credentials should be protected."""
        assert any(".aws" in p for p in ProtectedFiles.PROTECTED_PATTERNS)

    def test_private_keys_protected(self):
        """Private key files should be protected."""
        assert any("id_rsa" in p for p in ProtectedFiles.PROTECTED_PATTERNS)
        assert any("id_ed25519" in p for p in ProtectedFiles.PROTECTED_PATTERNS)

    def test_secrets_yaml_protected(self):
        """Secrets YAML should be protected."""
        assert any("secrets" in p for p in ProtectedFiles.PROTECTED_PATTERNS)


class TestWriteOnlyPatterns:
    """Tests for write-only protected patterns."""

    def test_package_lock_write_only(self):
        """package-lock.json should be write-protected."""
        assert any("package-lock" in p for p in ProtectedFiles.WRITE_ONLY_PATTERNS)

    def test_yarn_lock_write_only(self):
        """yarn.lock should be write-protected."""
        # Pattern uses regex: yarn\.lock$
        assert any("yarn" in p for p in ProtectedFiles.WRITE_ONLY_PATTERNS)

    def test_cargo_lock_write_only(self):
        """Cargo.lock should be write-protected."""
        # Pattern uses regex: Cargo\.lock$
        assert any("Cargo" in p for p in ProtectedFiles.WRITE_ONLY_PATTERNS)


class TestAllowedPaths:
    """Tests for allowed path overrides."""

    def test_env_example_allowed(self):
        """Example env files should be allowed."""
        # Pattern uses regex: \.env\.example$
        assert any("example" in p for p in ProtectedFiles.ALLOWED_PATHS)

    def test_env_sample_allowed(self):
        """Sample env files should be allowed."""
        # Pattern uses regex: \.env\.sample$
        assert any("sample" in p for p in ProtectedFiles.ALLOWED_PATHS)

    def test_env_template_allowed(self):
        """Template env files should be allowed."""
        # Pattern uses regex: \.env\.template$
        assert any("template" in p for p in ProtectedFiles.ALLOWED_PATHS)


class TestPatternsMatchGlob:
    """Tests for glob pattern matching utility."""

    def test_matches_exact_pattern(self):
        """Should match exact patterns."""
        patterns = ["*.py"]
        assert Patterns.matches_glob("test.py", patterns) is not None

    def test_matches_path_pattern(self):
        """Should match path patterns."""
        patterns = [".env"]
        assert Patterns.matches_glob("/home/user/.env", patterns) is not None

    def test_no_match_returns_none(self):
        """Should return None when no match."""
        patterns = ["*.py"]
        assert Patterns.matches_glob("test.js", patterns) is None

    def test_returns_matching_pattern(self):
        """Should return the matching pattern."""
        patterns = ["*.py", "*.js"]
        result = Patterns.matches_glob("test.py", patterns)
        assert result == "*.py"


class TestExpandPath:
    """Tests for path expansion utility."""

    def test_expands_home(self):
        """Should expand ~ to home directory."""
        path = expand_path("~/.env")
        assert "~" not in path
        assert path.startswith("/")

    def test_normalizes_path(self):
        """Should normalize path."""
        path = expand_path("/home/user/../user/file.txt")
        assert ".." not in path

    def test_handles_absolute_path(self):
        """Should handle absolute paths."""
        path = expand_path("/etc/passwd")
        assert path == "/etc/passwd"

    def test_handles_relative_path(self):
        """Should handle relative paths."""
        path = expand_path("./file.txt")
        assert path == "file.txt"

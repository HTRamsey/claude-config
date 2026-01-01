"""Tests for smart_permissions module."""
import sys
from pathlib import Path

import pytest

from smart_permissions import (
    READ_AUTO_APPROVE,
    WRITE_AUTO_APPROVE,
    NEVER_AUTO_APPROVE,
    APPROVAL_THRESHOLD,
    matches_any,
)


class TestApprovalThreshold:
    """Tests for approval threshold."""

    def test_threshold_is_positive(self):
        """Approval threshold should be positive."""
        assert APPROVAL_THRESHOLD > 0

    def test_threshold_is_reasonable(self):
        """Approval threshold should be reasonable (1-10)."""
        assert 1 <= APPROVAL_THRESHOLD <= 10


class TestReadAutoApprove:
    """Tests for read auto-approve patterns."""

    def test_markdown_approved(self):
        """Markdown files should be auto-approved."""
        assert matches_any("README.md", READ_AUTO_APPROVE)

    def test_txt_approved(self):
        """Text files should be auto-approved."""
        assert matches_any("notes.txt", READ_AUTO_APPROVE)

    def test_json_approved(self):
        """JSON files should be auto-approved."""
        assert matches_any("config.json", READ_AUTO_APPROVE)

    def test_yaml_approved(self):
        """YAML files should be auto-approved."""
        assert matches_any("config.yaml", READ_AUTO_APPROVE)
        assert matches_any("config.yml", READ_AUTO_APPROVE)

    def test_test_files_approved(self):
        """Test files should be auto-approved."""
        assert matches_any("test_module.py", READ_AUTO_APPROVE)
        assert matches_any("module_test.py", READ_AUTO_APPROVE)
        assert matches_any("tests/test_foo.py", READ_AUTO_APPROVE)

    def test_lock_files_approved(self):
        """Lock files should be auto-approved for read."""
        assert matches_any("package-lock.json", READ_AUTO_APPROVE)
        assert matches_any("yarn.lock", READ_AUTO_APPROVE)

    def test_type_definitions_approved(self):
        """Type definition files should be auto-approved."""
        assert matches_any("types.d.ts", READ_AUTO_APPROVE)
        assert matches_any("types.pyi", READ_AUTO_APPROVE)


class TestWriteAutoApprove:
    """Tests for write auto-approve patterns."""

    def test_test_files_approved(self):
        """Test files should be auto-approved for write."""
        assert matches_any("test_module.py", WRITE_AUTO_APPROVE)
        assert matches_any("module.test.js", WRITE_AUTO_APPROVE)

    def test_fixtures_dir_approved(self):
        """Fixtures directory should be auto-approved for write."""
        assert matches_any("fixtures/data.json", WRITE_AUTO_APPROVE)

    def test_mock_files_approved(self):
        """Mock files should be auto-approved for write."""
        assert matches_any("__mocks__/api.js", WRITE_AUTO_APPROVE)
        assert matches_any("mocks/api.js", WRITE_AUTO_APPROVE)


class TestNeverAutoApprove:
    """Tests for never auto-approve patterns."""

    def test_env_blocked(self):
        """Env files should never be auto-approved."""
        assert matches_any(".env", NEVER_AUTO_APPROVE)
        assert matches_any(".env.local", NEVER_AUTO_APPROVE)

    def test_secrets_blocked(self):
        """Secret files should never be auto-approved."""
        assert matches_any("secrets.yaml", NEVER_AUTO_APPROVE)
        assert matches_any("secrets.yml", NEVER_AUTO_APPROVE)

    def test_credentials_blocked(self):
        """Credential files should never be auto-approved."""
        assert matches_any("credentials.json", NEVER_AUTO_APPROVE)

    def test_ssh_keys_blocked(self):
        """SSH keys should never be auto-approved."""
        assert matches_any("id_rsa", NEVER_AUTO_APPROVE)
        assert matches_any(".ssh/config", NEVER_AUTO_APPROVE)

    def test_aws_blocked(self):
        """AWS credentials should never be auto-approved."""
        assert matches_any(".aws/credentials", NEVER_AUTO_APPROVE)


class TestMatchesAny:
    """Tests for matches_any function."""

    def test_empty_patterns(self):
        """Should return False for empty patterns."""
        assert matches_any("test.py", []) is False

    def test_no_match(self):
        """Should return False when no patterns match."""
        import re
        patterns = [re.compile(r"\.txt$")]
        assert matches_any("test.py", patterns) is False

    def test_match(self):
        """Should return True when pattern matches."""
        import re
        patterns = [re.compile(r"\.py$")]
        assert matches_any("test.py", patterns) is True

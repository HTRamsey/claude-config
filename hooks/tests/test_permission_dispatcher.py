"""Tests for permission_dispatcher module."""
import sys
from pathlib import Path

import pytest

from hooks.dispatchers.permission import (
    get_read_patterns,
    get_write_patterns,
    get_never_patterns,
    APPROVAL_THRESHOLD,
)
from hooks.hook_sdk import Patterns

# Get compiled patterns for tests
READ_AUTO_APPROVE = get_read_patterns()
WRITE_AUTO_APPROVE = get_write_patterns()
NEVER_AUTO_APPROVE = get_never_patterns()


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
        assert Patterns.matches_compiled("README.md", READ_AUTO_APPROVE)

    def test_txt_approved(self):
        """Text files should be auto-approved."""
        assert Patterns.matches_compiled("notes.txt", READ_AUTO_APPROVE)

    def test_json_approved(self):
        """JSON files should be auto-approved."""
        assert Patterns.matches_compiled("config.json", READ_AUTO_APPROVE)

    def test_yaml_approved(self):
        """YAML files should be auto-approved."""
        assert Patterns.matches_compiled("config.yaml", READ_AUTO_APPROVE)
        assert Patterns.matches_compiled("config.yml", READ_AUTO_APPROVE)

    def test_test_files_approved(self):
        """Test files should be auto-approved."""
        assert Patterns.matches_compiled("test_module.py", READ_AUTO_APPROVE)
        assert Patterns.matches_compiled("module_test.py", READ_AUTO_APPROVE)
        assert Patterns.matches_compiled("tests/test_foo.py", READ_AUTO_APPROVE)

    def test_lock_files_approved(self):
        """Lock files should be auto-approved for read."""
        assert Patterns.matches_compiled("package-lock.json", READ_AUTO_APPROVE)
        assert Patterns.matches_compiled("yarn.lock", READ_AUTO_APPROVE)

    def test_type_definitions_approved(self):
        """Type definition files should be auto-approved."""
        assert Patterns.matches_compiled("types.d.ts", READ_AUTO_APPROVE)
        assert Patterns.matches_compiled("types.pyi", READ_AUTO_APPROVE)


class TestWriteAutoApprove:
    """Tests for write auto-approve patterns."""

    def test_test_files_approved(self):
        """Test files should be auto-approved for write."""
        assert Patterns.matches_compiled("test_module.py", WRITE_AUTO_APPROVE)
        assert Patterns.matches_compiled("module.test.js", WRITE_AUTO_APPROVE)

    def test_fixtures_dir_approved(self):
        """Fixtures directory should be auto-approved for write."""
        assert Patterns.matches_compiled("fixtures/data.json", WRITE_AUTO_APPROVE)

    def test_mock_files_approved(self):
        """Mock files should be auto-approved for write."""
        assert Patterns.matches_compiled("__mocks__/api.js", WRITE_AUTO_APPROVE)
        assert Patterns.matches_compiled("mocks/api.js", WRITE_AUTO_APPROVE)


class TestNeverAutoApprove:
    """Tests for never auto-approve patterns."""

    def test_env_blocked(self):
        """Env files should never be auto-approved."""
        assert Patterns.matches_compiled(".env", NEVER_AUTO_APPROVE)
        assert Patterns.matches_compiled(".env.local", NEVER_AUTO_APPROVE)

    def test_secrets_blocked(self):
        """Secret files should never be auto-approved."""
        assert Patterns.matches_compiled("secrets.yaml", NEVER_AUTO_APPROVE)
        assert Patterns.matches_compiled("secrets.yml", NEVER_AUTO_APPROVE)

    def test_credentials_blocked(self):
        """Credential files should never be auto-approved."""
        assert Patterns.matches_compiled("credentials.json", NEVER_AUTO_APPROVE)

    def test_ssh_keys_blocked(self):
        """SSH keys should never be auto-approved."""
        assert Patterns.matches_compiled("id_rsa", NEVER_AUTO_APPROVE)
        assert Patterns.matches_compiled(".ssh/config", NEVER_AUTO_APPROVE)

    def test_aws_blocked(self):
        """AWS credentials should never be auto-approved."""
        assert Patterns.matches_compiled(".aws/credentials", NEVER_AUTO_APPROVE)


class TestMatchesCompiled:
    """Tests for Patterns.matches_compiled method."""

    def test_empty_patterns(self):
        """Should return False for empty patterns."""
        assert Patterns.matches_compiled("test.py", []) is False

    def test_no_match(self):
        """Should return False when no patterns match."""
        import re
        patterns = [re.compile(r"\.txt$")]
        assert Patterns.matches_compiled("test.py", patterns) is False

    def test_match(self):
        """Should return True when pattern matches."""
        import re
        patterns = [re.compile(r"\.py$")]
        assert Patterns.matches_compiled("test.py", patterns) is True

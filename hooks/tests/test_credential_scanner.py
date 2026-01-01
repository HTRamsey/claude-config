"""Tests for credential_scanner module."""
import sys
from pathlib import Path

import pytest

from hooks.handlers.credential_scanner import (
    is_allowlisted,
    scan_for_sensitive,
    get_compiled_patterns,
)
from hooks.config import Credentials

# Use config-based pattern access
SENSITIVE_PATTERNS = Credentials.sensitive_patterns
ALLOWLIST_PATTERNS = Credentials.allowlist_patterns


class TestSensitivePatterns:
    """Tests for sensitive pattern definitions."""

    def test_patterns_is_sequence(self):
        """Patterns should be a sequence (list or tuple)."""
        assert isinstance(SENSITIVE_PATTERNS, (list, tuple))

    def test_patterns_have_names(self):
        """Each pattern should have a name."""
        for pattern, name in SENSITIVE_PATTERNS:
            assert isinstance(name, str)
            assert len(name) > 0

    def test_patterns_are_valid_regex(self):
        """All patterns should compile as valid regex."""
        compiled = get_compiled_patterns()
        assert len(compiled) == len(SENSITIVE_PATTERNS)


class TestIsAllowlisted:
    """Tests for allowlist checking."""

    def test_example_file_allowed(self):
        """Example files should be allowlisted."""
        assert is_allowlisted(".env.example") is True
        assert is_allowlisted("config.example.json") is True

    def test_sample_file_allowed(self):
        """Sample files should be allowlisted."""
        assert is_allowlisted("settings.sample") is True

    def test_template_file_allowed(self):
        """Template files should be allowlisted."""
        assert is_allowlisted(".env.template") is True

    def test_test_file_allowed(self):
        """Test files should be allowlisted."""
        assert is_allowlisted("test_config.py") is True
        assert is_allowlisted("tests/test_api.py") is True

    def test_mock_file_allowed(self):
        """Mock files should be allowlisted."""
        assert is_allowlisted("mock_credentials.py") is True

    def test_real_env_not_allowed(self):
        """Real .env file should not be allowlisted."""
        assert is_allowlisted(".env") is False

    def test_production_config_not_allowed(self):
        """Production configs should not be allowlisted."""
        assert is_allowlisted("config.production.json") is False


class TestScanForSensitive:
    """Tests for sensitive data scanning."""

    def test_detects_aws_access_key(self):
        """Should detect AWS Access Key ID."""
        content = "AKIAIOSFODNN7EXAMPLE"
        findings = scan_for_sensitive(content)
        assert len(findings) > 0
        assert any("AWS" in name for name, _ in findings)

    def test_detects_github_pat(self):
        """Should detect GitHub PAT."""
        content = "ghp_abcdefghijklmnopqrstuvwxyzABCDEFGH12"
        findings = scan_for_sensitive(content)
        assert len(findings) > 0
        assert any("GitHub" in name for name, _ in findings)

    def test_detects_openai_key(self):
        """Should detect OpenAI API key pattern."""
        content = "sk-" + "a" * 48
        findings = scan_for_sensitive(content)
        assert len(findings) > 0
        assert any("OpenAI" in name for name, _ in findings)

    def test_detects_stripe_key(self):
        """Should detect Stripe secret key."""
        content = "sk_live_" + "a" * 24
        findings = scan_for_sensitive(content)
        assert len(findings) > 0
        assert any("Stripe" in name for name, _ in findings)

    def test_detects_private_key(self):
        """Should detect private key header."""
        content = "-----BEGIN RSA PRIVATE KEY-----"
        findings = scan_for_sensitive(content)
        assert len(findings) > 0
        assert any("Private key" in name for name, _ in findings)

    def test_detects_database_uri(self):
        """Should detect database URI with password."""
        content = "postgresql://user:secretpass@localhost/db"
        findings = scan_for_sensitive(content)
        assert len(findings) > 0
        assert any("Database" in name or "password" in name.lower() for name, _ in findings)

    def test_detects_hardcoded_password(self):
        """Should detect hardcoded password patterns."""
        content = 'password = "supersecret123"'
        findings = scan_for_sensitive(content)
        assert len(findings) > 0

    def test_ignores_safe_content(self):
        """Should not flag normal content."""
        content = "const message = 'Hello, World!';"
        findings = scan_for_sensitive(content)
        assert len(findings) == 0

    def test_truncates_long_matches(self):
        """Should truncate long matches."""
        content = "AKIAIOSFODNN7EXAMPLE" + "X" * 100
        findings = scan_for_sensitive(content)
        for _, match in findings:
            assert len(match) <= 23  # 20 + "..."

    def test_limits_matches_per_pattern(self):
        """Should limit matches per pattern."""
        # Multiple AWS keys
        content = "\n".join([f"AKIA{'X' * 16}" for _ in range(10)])
        findings = scan_for_sensitive(content)
        # Should not have more than 3 AWS key findings
        aws_findings = [f for f in findings if "AWS" in f[0]]
        assert len(aws_findings) <= 3


class TestAllowlistPatterns:
    """Tests for allowlist pattern configuration."""

    def test_allowlist_has_patterns(self):
        """Allowlist should have patterns defined."""
        assert len(ALLOWLIST_PATTERNS) > 0

    def test_common_patterns_present(self):
        """Common safe patterns should be present."""
        assert "test" in ALLOWLIST_PATTERNS
        assert ".example" in ALLOWLIST_PATTERNS

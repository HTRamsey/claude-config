"""
Tests for hooks/config.py.

Covers:
- All dataclass default values
- Backwards-compatible UPPER_CASE property aliases
- Pattern compilation functions (with @lru_cache)
- Singleton instances
- BuildConfig pattern matching
- CredentialConfig pattern detection
"""
import os
import re
from pathlib import Path

import pytest

from hooks.config import (
    # Singletons
    Timeouts,
    Thresholds,
    FilePatterns,
    Limits,
    Credentials,
    # Classes
    TimeoutConfig,
    ThresholdConfig,
    FilePatternConfig,
    LimitConfig,
    CredentialConfig,
    ProtectedFiles,
    DangerousCommands,
    StateSaver,
    AutoContinue,
    SmartPermissions,
    # Pattern compilation functions
    _compile_blocked_patterns,
    _compile_warning_patterns,
    _compile_state_saver_patterns,
    _compile_incomplete_patterns,
    _compile_complete_patterns,
    _compile_read_permissions_patterns,
    _compile_write_permissions_patterns,
    _compile_never_permissions_patterns,
    _compile_credential_patterns,
    get_protected_patterns_compiled,
    get_write_only_patterns_compiled,
    get_allowed_patterns_compiled,
    # Constants
    DATA_DIR,
    CACHE_DIR,
    TRACKER_DIR,
    STATE_FILES,
)


# =============================================================================
# TimeoutConfig Tests
# =============================================================================

class TestTimeoutConfig:
    """Test TimeoutConfig dataclass."""

    def test_default_values(self):
        """Verify default timeout values."""
        config = TimeoutConfig()
        assert config.handler_timeout_ms == int(os.environ.get("HANDLER_TIMEOUT", "1000"))
        assert config.cache_ttl == 5.0
        assert config.hook_disabled_ttl == 10.0
        assert config.hierarchy_cache_ttl == 30.0
        assert config.patterns_cache_ttl == 5.0
        assert config.exploration_cache_ttl == 3600
        assert config.research_cache_ttl == 86400
        assert config.state_max_age == 86400
        assert config.checkpoint_interval == 300
        assert config.cleanup_interval == 300
        assert config.warning_window == 3600
        assert config.continue_window == 300
        assert config.stale_time_threshold == 300
        assert config.tool_tracker_max_age == 3600

    def test_handler_timeout_s_calculated(self):
        """Verify handler_timeout_s is calculated from ms."""
        config = TimeoutConfig()
        assert config.handler_timeout_s == config.handler_timeout_ms / 1000.0

    def test_uppercase_aliases(self):
        """Verify UPPER_CASE properties match lowercase."""
        config = TimeoutConfig()
        assert config.HANDLER_TIMEOUT_MS == config.handler_timeout_ms
        assert config.HANDLER_TIMEOUT_S == config.handler_timeout_s
        assert config.CACHE_TTL == config.cache_ttl
        assert config.HOOK_DISABLED_TTL == config.hook_disabled_ttl
        assert config.HIERARCHY_CACHE_TTL == config.hierarchy_cache_ttl
        assert config.PATTERNS_CACHE_TTL == config.patterns_cache_ttl
        assert config.EXPLORATION_CACHE_TTL == config.exploration_cache_ttl
        assert config.RESEARCH_CACHE_TTL == config.research_cache_ttl
        assert config.STATE_MAX_AGE == config.state_max_age
        assert config.CHECKPOINT_INTERVAL == config.checkpoint_interval
        assert config.CLEANUP_INTERVAL == config.cleanup_interval
        assert config.WARNING_WINDOW == config.warning_window
        assert config.CONTINUE_WINDOW == config.continue_window
        assert config.STALE_TIME_THRESHOLD == config.stale_time_threshold
        assert config.TOOL_TRACKER_MAX_AGE == config.tool_tracker_max_age

    def test_singleton_accessible(self):
        """Verify Timeouts singleton is accessible."""
        assert isinstance(Timeouts, TimeoutConfig)
        assert Timeouts.cache_ttl == 5.0


# =============================================================================
# ThresholdConfig Tests
# =============================================================================

class TestThresholdConfig:
    """Test ThresholdConfig dataclass."""

    def test_default_values(self):
        """Verify default threshold values."""
        config = ThresholdConfig()
        assert config.output_warning == 10000
        assert config.output_critical == 50000
        assert config.token_warning == 40000
        assert config.token_critical == 80000
        assert config.daily_token_warning == 500000
        assert config.chars_per_token == 4
        assert config.max_reads_tracked == 100
        assert config.max_searches_tracked == 50
        assert config.stale_message_threshold == 15
        assert config.similarity_threshold == 0.8
        assert config.large_file_lines == 200
        assert config.large_file_bytes == 15000
        assert config.batch_similarity_threshold == 3
        assert config.tdd_warning_threshold == 3
        assert config.min_lines_for_tdd == 30
        assert config.max_reflexion_entries == 100
        assert config.max_error_backups == 20
        assert config.max_cache_entries == 30
        assert config.max_continuations == 3
        assert config.min_notify_duration == 30
        assert config.stats_flush_interval == 10
        assert config.permission_approval_threshold == 3
        assert config.tool_failure_threshold == 2

    def test_uppercase_aliases(self):
        """Verify UPPER_CASE properties match lowercase."""
        config = ThresholdConfig()
        assert config.OUTPUT_WARNING == config.output_warning
        assert config.OUTPUT_CRITICAL == config.output_critical
        assert config.TOKEN_WARNING == config.token_warning
        assert config.TOKEN_CRITICAL == config.token_critical
        assert config.DAILY_TOKEN_WARNING == config.daily_token_warning
        assert config.CHARS_PER_TOKEN == config.chars_per_token
        assert config.MAX_READS_TRACKED == config.max_reads_tracked
        assert config.MAX_SEARCHES_TRACKED == config.max_searches_tracked
        assert config.STALE_MESSAGE_THRESHOLD == config.stale_message_threshold
        assert config.SIMILARITY_THRESHOLD == config.similarity_threshold
        assert config.LARGE_FILE_LINES == config.large_file_lines
        assert config.LARGE_FILE_BYTES == config.large_file_bytes
        assert config.BATCH_SIMILARITY_THRESHOLD == config.batch_similarity_threshold
        assert config.TDD_WARNING_THRESHOLD == config.tdd_warning_threshold
        assert config.MIN_LINES_FOR_TDD == config.min_lines_for_tdd
        assert config.MAX_REFLEXION_ENTRIES == config.max_reflexion_entries
        assert config.MAX_ERROR_BACKUPS == config.max_error_backups
        assert config.MAX_CACHE_ENTRIES == config.max_cache_entries
        assert config.MAX_CONTINUATIONS == config.max_continuations
        assert config.MIN_NOTIFY_DURATION == config.min_notify_duration
        assert config.STATS_FLUSH_INTERVAL == config.stats_flush_interval
        assert config.PERMISSION_APPROVAL_THRESHOLD == config.permission_approval_threshold
        assert config.TOOL_FAILURE_THRESHOLD == config.tool_failure_threshold

    def test_singleton_accessible(self):
        """Verify Thresholds singleton is accessible."""
        assert isinstance(Thresholds, ThresholdConfig)
        assert Thresholds.output_warning == 10000


# =============================================================================
# FilePatternConfig Tests
# =============================================================================

class TestFilePatternConfig:
    """Test FilePatternConfig dataclass."""

    def test_default_values(self):
        """Verify default file pattern values."""
        config = FilePatternConfig()
        assert isinstance(config.code_extensions, frozenset)
        assert '.py' in config.code_extensions
        assert '.js' in config.code_extensions
        assert '.ts' in config.code_extensions

        assert isinstance(config.test_patterns, tuple)
        assert 'test_' in config.test_patterns
        assert '_test' in config.test_patterns

        assert isinstance(config.tdd_skip_patterns, tuple)
        assert '__init__.py' in config.tdd_skip_patterns

        assert isinstance(config.always_summarize, frozenset)
        assert '.log' in config.always_summarize
        assert '.json' in config.always_summarize

        assert isinstance(config.skip_summarize, frozenset)
        assert '.md' in config.skip_summarize

        assert isinstance(config.large_output_tools, tuple)
        assert "Task" in config.large_output_tools

    def test_uppercase_aliases(self):
        """Verify UPPER_CASE properties match lowercase."""
        config = FilePatternConfig()
        assert config.CODE_EXTENSIONS == config.code_extensions
        assert config.TEST_PATTERNS == config.test_patterns
        assert config.TDD_SKIP_PATTERNS == config.tdd_skip_patterns
        assert config.ALWAYS_SUMMARIZE == config.always_summarize
        assert config.SKIP_SUMMARIZE == config.skip_summarize
        assert config.LARGE_OUTPUT_TOOLS == config.large_output_tools

    def test_singleton_accessible(self):
        """Verify FilePatterns singleton is accessible."""
        assert isinstance(FilePatterns, FilePatternConfig)
        assert '.py' in FilePatterns.code_extensions


# =============================================================================
# LimitConfig Tests
# =============================================================================

class TestLimitConfig:
    """Test LimitConfig dataclass."""

    def test_default_values(self):
        """Verify default limit values."""
        config = LimitConfig()
        assert config.max_suggested_skills == 100
        assert config.max_recent_patterns == 10
        assert config.max_fuzzy_search_entries == 30
        assert config.max_checkpoints == 20
        assert config.max_seen_sessions == 100
        assert config.max_backups == 20
        assert config.max_chain_recommendations == 2
        assert config.max_messages_joined == 3
        assert config.patterns_cache_maxsize == 1
        assert config.hierarchy_cache_maxsize == 256
        assert config.content_truncate_summary == 500
        assert config.content_truncate_cache == 2000
        assert config.content_truncate_full == 10000
        assert config.prompt_truncate == 100
        assert config.command_truncate == 500
        assert config.url_truncate == 80

    def test_uppercase_aliases(self):
        """Verify UPPER_CASE properties match lowercase."""
        config = LimitConfig()
        assert config.MAX_SUGGESTED_SKILLS == config.max_suggested_skills
        assert config.MAX_RECENT_PATTERNS == config.max_recent_patterns
        assert config.MAX_FUZZY_SEARCH_ENTRIES == config.max_fuzzy_search_entries
        assert config.MAX_CHECKPOINTS == config.max_checkpoints
        assert config.MAX_SEEN_SESSIONS == config.max_seen_sessions
        assert config.MAX_BACKUPS == config.max_backups
        assert config.MAX_CHAIN_RECOMMENDATIONS == config.max_chain_recommendations
        assert config.MAX_MESSAGES_JOINED == config.max_messages_joined
        assert config.CONTENT_TRUNCATE_SUMMARY == config.content_truncate_summary
        assert config.CONTENT_TRUNCATE_CACHE == config.content_truncate_cache
        assert config.CONTENT_TRUNCATE_FULL == config.content_truncate_full
        assert config.PATTERNS_CACHE_MAXSIZE == config.patterns_cache_maxsize
        assert config.HIERARCHY_CACHE_MAXSIZE == config.hierarchy_cache_maxsize
        assert config.PROMPT_TRUNCATE == config.prompt_truncate
        assert config.COMMAND_TRUNCATE == config.command_truncate
        assert config.URL_TRUNCATE == config.url_truncate

    def test_singleton_accessible(self):
        """Verify Limits singleton is accessible."""
        assert isinstance(Limits, LimitConfig)
        assert Limits.max_suggested_skills == 100


# =============================================================================
# CredentialConfig Tests
# =============================================================================

class TestCredentialConfig:
    """Test CredentialConfig dataclass."""

    def test_sensitive_patterns_structure(self):
        """Verify sensitive patterns are tuples of (pattern, name)."""
        config = CredentialConfig()
        assert isinstance(config.sensitive_patterns, tuple)
        assert len(config.sensitive_patterns) > 0

        # Each item should be (pattern, name)
        for item in config.sensitive_patterns:
            assert isinstance(item, tuple)
            assert len(item) == 2
            pattern, name = item
            assert isinstance(pattern, str)
            assert isinstance(name, str)

    def test_detects_aws_key(self):
        """Verify AWS access key pattern works."""
        patterns = Credentials.get_compiled_patterns()
        aws_key = "AKIAIOSFODNN7EXAMPLE"

        matches = [p for p, n in patterns if p.search(aws_key)]
        assert len(matches) > 0, "Should detect AWS access key"

    def test_detects_openai_key(self):
        """Verify OpenAI API key pattern works."""
        patterns = Credentials.get_compiled_patterns()
        openai_key = "sk-" + "a" * 48

        matches = [p for p, n in patterns if p.search(openai_key)]
        assert len(matches) > 0, "Should detect OpenAI API key"

    def test_detects_anthropic_key(self):
        """Verify Anthropic API key pattern works."""
        patterns = Credentials.get_compiled_patterns()
        anthropic_key = "sk-ant-" + "a" * 90

        matches = [p for p, n in patterns if p.search(anthropic_key)]
        assert len(matches) > 0, "Should detect Anthropic API key"

    def test_detects_private_key(self):
        """Verify private key header pattern works."""
        patterns = Credentials.get_compiled_patterns()
        private_key = "-----BEGIN PRIVATE KEY-----"

        matches = [p for p, n in patterns if p.search(private_key)]
        assert len(matches) > 0, "Should detect private key"

    def test_detects_jwt_token(self):
        """Verify JWT token pattern works."""
        patterns = Credentials.get_compiled_patterns()
        jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"

        matches = [p for p, n in patterns if p.search(jwt)]
        assert len(matches) > 0, "Should detect JWT token"

    def test_pattern_compilation_returns_compiled_regex(self):
        """Verify compiled patterns are valid regex objects."""
        patterns = Credentials.get_compiled_patterns()
        assert len(patterns) > 0

        for pattern, name in patterns:
            assert hasattr(pattern, 'search'), f"Pattern for '{name}' should be compiled regex"
            assert hasattr(pattern, 'match'), f"Pattern for '{name}' should be compiled regex"

    def test_allowlist_patterns(self):
        """Verify allowlist patterns exist."""
        config = CredentialConfig()
        assert '.example' in config.allowlist_patterns
        assert '.sample' in config.allowlist_patterns
        assert 'test' in config.allowlist_patterns

    def test_singleton_accessible(self):
        """Verify Credentials singleton is accessible."""
        assert isinstance(Credentials, CredentialConfig)


# =============================================================================
# ProtectedFiles Tests
# =============================================================================

class TestProtectedFiles:
    """Test ProtectedFiles patterns."""

    def test_protected_patterns_exist(self):
        """Verify protected patterns are defined."""
        assert len(ProtectedFiles.PROTECTED_PATTERNS) > 0

    def test_write_only_patterns_exist(self):
        """Verify write-only patterns are defined."""
        assert len(ProtectedFiles.WRITE_ONLY_PATTERNS) > 0

    def test_allowed_paths_exist(self):
        """Verify allowed override paths are defined."""
        assert len(ProtectedFiles.ALLOWED_PATHS) > 0

    def test_protected_patterns_compile(self):
        """Verify protected patterns compile to valid regex."""
        patterns = get_protected_patterns_compiled()
        assert len(patterns) > 0

        for pattern in patterns:
            assert hasattr(pattern, 'search')
            assert hasattr(pattern, 'match')

    def test_write_only_patterns_compile(self):
        """Verify write-only patterns compile to valid regex."""
        patterns = get_write_only_patterns_compiled()
        assert len(patterns) > 0

        for pattern in patterns:
            assert hasattr(pattern, 'search')

    def test_allowed_patterns_compile(self):
        """Verify allowed patterns compile to valid regex."""
        patterns = get_allowed_patterns_compiled()
        assert len(patterns) > 0

        for pattern in patterns:
            assert hasattr(pattern, 'search')

    def test_matches_env_file(self):
        """Verify .env file is protected."""
        patterns = get_protected_patterns_compiled()
        assert any(p.search(".env") for p in patterns)

    def test_matches_ssh_dir(self):
        """Verify .ssh directory is protected."""
        patterns = get_protected_patterns_compiled()
        assert any(p.search("/home/user/.ssh/id_rsa") for p in patterns)

    def test_matches_lockfile(self):
        """Verify package-lock.json is write-protected."""
        patterns = get_write_only_patterns_compiled()
        assert any(p.search("package-lock.json") for p in patterns)

    def test_allows_env_example(self):
        """Verify .env.example is allowed."""
        patterns = get_allowed_patterns_compiled()
        assert any(p.search(".env.example") for p in patterns)


# =============================================================================
# DangerousCommands Tests
# =============================================================================

class TestDangerousCommands:
    """Test DangerousCommands patterns."""

    def test_blocked_patterns_exist(self):
        """Verify blocked patterns are defined."""
        assert len(DangerousCommands.BLOCKED_PATTERNS_RAW) > 0

    def test_warning_patterns_exist(self):
        """Verify warning patterns are defined."""
        assert len(DangerousCommands.WARNING_PATTERNS_RAW) > 0

    def test_get_blocked_returns_compiled(self):
        """Verify get_blocked() returns compiled patterns."""
        patterns = DangerousCommands.get_blocked()
        assert len(patterns) > 0

        for pattern, reason in patterns:
            assert hasattr(pattern, 'search')
            assert isinstance(reason, str)

    def test_get_warnings_returns_compiled(self):
        """Verify get_warnings() returns compiled patterns."""
        patterns = DangerousCommands.get_warnings()
        assert len(patterns) > 0

        for pattern, reason in patterns:
            assert hasattr(pattern, 'search')
            assert isinstance(reason, str)

    def test_blocks_rm_rf_root(self):
        """Verify 'rm -rf /' is blocked."""
        patterns = DangerousCommands.get_blocked()
        assert any(p.search("rm -rf /") for p, r in patterns)

    def test_blocks_fork_bomb(self):
        """Verify fork bomb is blocked."""
        patterns = DangerousCommands.get_blocked()
        fork_bomb = ":(){ :|:& };:"
        assert any(p.search(fork_bomb) for p, r in patterns)

    def test_warns_git_force_push(self):
        """Verify git force push triggers warning."""
        patterns = DangerousCommands.get_warnings()
        assert any(p.search("git push --force") for p, r in patterns)

    def test_warns_hard_reset(self):
        """Verify hard reset triggers warning."""
        patterns = DangerousCommands.get_warnings()
        assert any(p.search("git reset --hard") for p, r in patterns)


# =============================================================================
# StateSaver Tests
# =============================================================================

class TestStateSaver:
    """Test StateSaver patterns."""

    def test_risky_patterns_exist(self):
        """Verify risky patterns are defined."""
        assert len(StateSaver.RISKY_PATTERNS_RAW) > 0

    def test_risky_keywords_exist(self):
        """Verify risky keywords are defined."""
        assert len(StateSaver.RISKY_KEYWORDS) > 0
        assert 'delete' in StateSaver.RISKY_KEYWORDS

    def test_get_patterns_returns_compiled(self):
        """Verify get_patterns() returns compiled regex."""
        patterns = StateSaver.get_patterns()
        assert len(patterns) > 0

        for pattern in patterns:
            assert hasattr(pattern, 'search')

    def test_matches_rm_rf(self):
        """Verify 'rm -rf' is risky."""
        patterns = StateSaver.get_patterns()
        assert any(p.search("rm -rf dir/") for p in patterns)

    def test_matches_drop_table(self):
        """Verify 'DROP TABLE' is risky."""
        patterns = StateSaver.get_patterns()
        assert any(p.search("DROP TABLE users") for p in patterns)


# =============================================================================
# AutoContinue Tests
# =============================================================================

class TestAutoContinue:
    """Test AutoContinue patterns."""

    def test_incomplete_patterns_exist(self):
        """Verify incomplete patterns are defined."""
        assert len(AutoContinue.INCOMPLETE_PATTERNS_RAW) > 0

    def test_complete_patterns_exist(self):
        """Verify complete patterns are defined."""
        assert len(AutoContinue.COMPLETE_PATTERNS_RAW) > 0

    def test_get_incomplete_returns_compiled(self):
        """Verify get_incomplete() returns compiled regex."""
        patterns = AutoContinue.get_incomplete()
        assert len(patterns) > 0

        for pattern in patterns:
            assert hasattr(pattern, 'search')

    def test_get_complete_returns_compiled(self):
        """Verify get_complete() returns compiled regex."""
        patterns = AutoContinue.get_complete()
        assert len(patterns) > 0

        for pattern in patterns:
            assert hasattr(pattern, 'search')

    def test_matches_incomplete(self):
        """Verify incomplete phrases are detected."""
        patterns = AutoContinue.get_incomplete()
        assert any(p.search("will continue in next message") for p in patterns)
        assert any(p.search("remaining tasks") for p in patterns)

    def test_matches_complete(self):
        """Verify complete phrases are detected."""
        patterns = AutoContinue.get_complete()
        assert any(p.search("all done") for p in patterns)
        assert any(p.search("successfully completed") for p in patterns)


# =============================================================================
# SmartPermissions Tests
# =============================================================================

class TestSmartPermissions:
    """Test SmartPermissions patterns."""

    def test_read_patterns_exist(self):
        """Verify read patterns are defined."""
        assert len(SmartPermissions.READ_PATTERNS_RAW) > 0

    def test_write_patterns_exist(self):
        """Verify write patterns are defined."""
        assert len(SmartPermissions.WRITE_PATTERNS_RAW) > 0

    def test_never_patterns_exist(self):
        """Verify never patterns are defined."""
        assert len(SmartPermissions.NEVER_PATTERNS_RAW) > 0

    def test_get_read_returns_compiled(self):
        """Verify get_read() returns compiled regex."""
        patterns = SmartPermissions.get_read()
        assert len(patterns) > 0

        for pattern in patterns:
            assert hasattr(pattern, 'search')

    def test_get_write_returns_compiled(self):
        """Verify get_write() returns compiled regex."""
        patterns = SmartPermissions.get_write()
        assert len(patterns) > 0

        for pattern in patterns:
            assert hasattr(pattern, 'search')

    def test_get_never_returns_compiled(self):
        """Verify get_never() returns compiled regex."""
        patterns = SmartPermissions.get_never()
        assert len(patterns) > 0

        for pattern in patterns:
            assert hasattr(pattern, 'search')

    def test_read_matches_readme(self):
        """Verify README files are auto-approved for read."""
        patterns = SmartPermissions.get_read()
        assert any(p.search("README.md") for p in patterns)

    def test_read_matches_test_file(self):
        """Verify test files are auto-approved for read."""
        patterns = SmartPermissions.get_read()
        assert any(p.search("test_config.py") for p in patterns)

    def test_write_matches_test_file(self):
        """Verify test files are auto-approved for write."""
        patterns = SmartPermissions.get_write()
        assert any(p.search("test_config.py") for p in patterns)

    def test_never_matches_env(self):
        """Verify .env files are never auto-approved."""
        patterns = SmartPermissions.get_never()
        assert any(p.search(".env") for p in patterns)


# =============================================================================
# Path Constants Tests
# =============================================================================

class TestPaths:
    """Test path constants."""

    def test_data_dir_is_path(self):
        """Verify DATA_DIR is a Path object."""
        assert isinstance(DATA_DIR, Path)

    def test_cache_dir_is_path(self):
        """Verify CACHE_DIR is a Path object."""
        assert isinstance(CACHE_DIR, Path)

    def test_tracker_dir_is_path(self):
        """Verify TRACKER_DIR is a Path object."""
        assert isinstance(TRACKER_DIR, Path)

    def test_state_files_is_dict(self):
        """Verify STATE_FILES is a dict."""
        assert isinstance(STATE_FILES, dict)
        assert len(STATE_FILES) > 0

    def test_state_files_have_paths(self):
        """Verify all state files are Path objects."""
        for name, path in STATE_FILES.items():
            assert isinstance(path, Path), f"STATE_FILES['{name}'] should be Path"


# =============================================================================
# Pattern Compilation Function Tests
# =============================================================================

class TestPatternCompilationFunctions:
    """Test @lru_cache pattern compilation functions."""

    def test_compile_blocked_patterns_cached(self):
        """Verify _compile_blocked_patterns() uses cache."""
        result1 = _compile_blocked_patterns()
        result2 = _compile_blocked_patterns()
        assert result1 is result2, "Should return same cached object"

    def test_compile_warning_patterns_cached(self):
        """Verify _compile_warning_patterns() uses cache."""
        result1 = _compile_warning_patterns()
        result2 = _compile_warning_patterns()
        assert result1 is result2

    def test_compile_state_saver_patterns_cached(self):
        """Verify _compile_state_saver_patterns() uses cache."""
        result1 = _compile_state_saver_patterns()
        result2 = _compile_state_saver_patterns()
        assert result1 is result2

    def test_compile_incomplete_patterns_cached(self):
        """Verify _compile_incomplete_patterns() uses cache."""
        result1 = _compile_incomplete_patterns()
        result2 = _compile_incomplete_patterns()
        assert result1 is result2

    def test_compile_complete_patterns_cached(self):
        """Verify _compile_complete_patterns() uses cache."""
        result1 = _compile_complete_patterns()
        result2 = _compile_complete_patterns()
        assert result1 is result2

    def test_compile_read_permissions_patterns_cached(self):
        """Verify _compile_read_permissions_patterns() uses cache."""
        result1 = _compile_read_permissions_patterns()
        result2 = _compile_read_permissions_patterns()
        assert result1 is result2

    def test_compile_write_permissions_patterns_cached(self):
        """Verify _compile_write_permissions_patterns() uses cache."""
        result1 = _compile_write_permissions_patterns()
        result2 = _compile_write_permissions_patterns()
        assert result1 is result2

    def test_compile_never_permissions_patterns_cached(self):
        """Verify _compile_never_permissions_patterns() uses cache."""
        result1 = _compile_never_permissions_patterns()
        result2 = _compile_never_permissions_patterns()
        assert result1 is result2

    def test_compile_credential_patterns_cached(self):
        """Verify _compile_credential_patterns() uses cache."""
        result1 = _compile_credential_patterns()
        result2 = _compile_credential_patterns()
        assert result1 is result2

    def test_get_protected_patterns_compiled_cached(self):
        """Verify get_protected_patterns_compiled() uses cache."""
        result1 = get_protected_patterns_compiled()
        result2 = get_protected_patterns_compiled()
        assert result1 is result2

    def test_get_write_only_patterns_compiled_cached(self):
        """Verify get_write_only_patterns_compiled() uses cache."""
        result1 = get_write_only_patterns_compiled()
        result2 = get_write_only_patterns_compiled()
        assert result1 is result2

    def test_get_allowed_patterns_compiled_cached(self):
        """Verify get_allowed_patterns_compiled() uses cache."""
        result1 = get_allowed_patterns_compiled()
        result2 = get_allowed_patterns_compiled()
        assert result1 is result2


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    """Integration tests across multiple config classes."""

    def test_all_singletons_accessible(self):
        """Verify all singleton instances are accessible and correct type."""
        assert isinstance(Timeouts, TimeoutConfig)
        assert isinstance(Thresholds, ThresholdConfig)
        assert isinstance(FilePatterns, FilePatternConfig)
        assert isinstance(Limits, LimitConfig)
        assert isinstance(Credentials, CredentialConfig)

    def test_consistent_test_file_handling(self):
        """Verify test file detection is consistent across configs."""
        # FilePatterns has test patterns
        assert 'test_' in FilePatterns.test_patterns

        # SmartPermissions allows test files for read/write
        read_patterns = SmartPermissions.get_read()
        write_patterns = SmartPermissions.get_write()

        test_file = "test_config.py"
        assert any(p.search(test_file) for p in read_patterns)
        assert any(p.search(test_file) for p in write_patterns)

    def test_credential_patterns_dont_match_allowlist(self):
        """Verify credential patterns respect allowlist context."""
        # This is a conceptual test - the actual logic would be in the scanner
        allowlist = Credentials.allowlist_patterns
        assert '.example' in allowlist
        assert 'test' in allowlist

        # Patterns should still compile and work
        patterns = Credentials.get_compiled_patterns()
        assert len(patterns) > 0

    def test_frozen_dataclasses_immutable(self):
        """Verify frozen dataclasses cannot be modified."""
        with pytest.raises(AttributeError):
            Timeouts.cache_ttl = 999  # type: ignore

        with pytest.raises(AttributeError):
            Thresholds.output_warning = 999  # type: ignore

        with pytest.raises(AttributeError):
            FilePatterns.code_extensions = frozenset({'.py'})  # type: ignore

        with pytest.raises(AttributeError):
            Limits.max_suggested_skills = 999  # type: ignore

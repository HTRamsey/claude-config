"""
Centralized configuration for Claude Code hooks.

All configurable constants in one place for easy tuning.
Individual hooks import from here for consistency.

Categories:
- Paths: Data directories and file locations
- Timeouts: TTLs, intervals, and durations
- Thresholds: Limits and warning levels
- Patterns: File extensions, regex patterns
- Limits: Size constraints for state management
"""
import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

# =============================================================================
# Paths
# =============================================================================

DATA_DIR = Path(os.environ.get("CLAUDE_DATA_DIR", Path.home() / ".claude/data"))
CACHE_DIR = DATA_DIR / "cache"
TRACKER_DIR = Path(os.environ.get("CLAUDE_TRACKER_DIR", DATA_DIR / "tracking"))

# Session state directories
SESSION_STATE_DIR = DATA_DIR / "sessions"
SESSION_STATE_FILE = DATA_DIR / "session-state.json"

# State files
STATE_FILES = {
    "checkpoint": DATA_DIR / "checkpoint-state.json",
    "auto_continue": DATA_DIR / "auto-continue-state.json",
    "reflexion": DATA_DIR / "reflexion-log.json",
    "permission_patterns": DATA_DIR / "permission-patterns.json",
    "usage_stats": DATA_DIR / "usage-stats.json",
    "hook_config": DATA_DIR / "hook-config.json",
    "hook_events": DATA_DIR / "hook-events.jsonl",
    "session_state": SESSION_STATE_FILE,
}

# =============================================================================
# Timeouts and Intervals (seconds)
# =============================================================================

@dataclass(frozen=True)
class TimeoutConfig:
    """Timeout and interval settings."""
    # Handler execution
    handler_timeout_ms: int = int(os.environ.get("HANDLER_TIMEOUT", "1000"))
    handler_timeout_s: float = None  # Set in __post_init__

    # Cache TTLs
    cache_ttl: float = 5.0  # In-memory cache TTL (seconds)
    hook_disabled_ttl: float = 10.0  # Hook disabled check cache TTL
    hierarchy_cache_ttl: float = 30.0  # Hierarchical rules cache (CLAUDE.md files rarely change)
    patterns_cache_ttl: float = 5.0  # Smart permissions learned patterns cache TTL
    exploration_cache_ttl: int = 3600  # 1 hour for exploration results
    research_cache_ttl: int = 86400  # 24 hours for web research

    # State management
    state_max_age: int = 86400  # Clear state after 24 hours
    checkpoint_interval: int = 300  # Min seconds between checkpoints
    cleanup_interval: int = 300  # Rate-limit cleanup operations

    # TDD guard
    warning_window: int = 3600  # 1 hour window for counting TDD warnings

    # Auto-continue
    continue_window: int = 300  # 5 minutes

    # Stale context
    stale_time_threshold: int = 300  # 5 minutes

    # Tool success tracker
    tool_tracker_max_age: int = 3600  # Clear tool tracker state after 1 hour

    # Daily stats cache
    daily_stats_cache_ttl: int = 300  # 5 minutes

    # Token cache (context monitor)
    token_cache_ttl: float = 60.0  # 1 minute

    def __post_init__(self):
        object.__setattr__(self, 'handler_timeout_s', self.handler_timeout_ms / 1000.0)

    # Backwards compatibility: UPPER_CASE aliases
    @property
    def HANDLER_TIMEOUT_MS(self) -> int:
        return self.handler_timeout_ms

    @property
    def HANDLER_TIMEOUT_S(self) -> float:
        return self.handler_timeout_s

    @property
    def CACHE_TTL(self) -> float:
        return self.cache_ttl

    @property
    def HOOK_DISABLED_TTL(self) -> float:
        return self.hook_disabled_ttl

    @property
    def HIERARCHY_CACHE_TTL(self) -> float:
        return self.hierarchy_cache_ttl

    @property
    def PATTERNS_CACHE_TTL(self) -> float:
        return self.patterns_cache_ttl

    @property
    def EXPLORATION_CACHE_TTL(self) -> int:
        return self.exploration_cache_ttl

    @property
    def RESEARCH_CACHE_TTL(self) -> int:
        return self.research_cache_ttl

    @property
    def STATE_MAX_AGE(self) -> int:
        return self.state_max_age

    @property
    def CHECKPOINT_INTERVAL(self) -> int:
        return self.checkpoint_interval

    @property
    def CLEANUP_INTERVAL(self) -> int:
        return self.cleanup_interval

    @property
    def WARNING_WINDOW(self) -> int:
        return self.warning_window

    @property
    def CONTINUE_WINDOW(self) -> int:
        return self.continue_window

    @property
    def STALE_TIME_THRESHOLD(self) -> int:
        return self.stale_time_threshold

    @property
    def TOOL_TRACKER_MAX_AGE(self) -> int:
        return self.tool_tracker_max_age

    @property
    def DAILY_STATS_CACHE_TTL(self) -> int:
        return self.daily_stats_cache_ttl

    @property
    def TOKEN_CACHE_TTL(self) -> float:
        return self.token_cache_ttl


# Create singleton instance with same name for backwards compatibility
Timeouts = TimeoutConfig()


# =============================================================================
# Thresholds and Limits
# =============================================================================

@dataclass(frozen=True)
class ThresholdConfig:
    """Warning thresholds and limits."""
    # Token/output warnings
    output_warning: int = 10000  # Warn if output > 10K chars
    output_critical: int = 50000  # Strong warning if > 50K chars
    token_warning: int = 40000  # Warn at 40K tokens
    token_critical: int = 80000  # Strong warning at 80K
    daily_token_warning: int = 500000  # Warn at 500K tokens/day
    chars_per_token: int = 4  # Rough estimate

    # File monitoring
    max_reads_tracked: int = 100
    max_searches_tracked: int = 50
    stale_message_threshold: int = 15  # Warn if read >15 messages ago
    similarity_threshold: float = 0.8  # Fuzzy pattern matching

    # Large file detection
    large_file_lines: int = 200
    large_file_bytes: int = 15000

    # Batch detection
    batch_similarity_threshold: int = 3  # Suggest after 3 similar ops

    # TDD guard
    tdd_warning_threshold: int = 3  # Block after this many warnings
    min_lines_for_tdd: int = 30

    # State limits
    max_reflexion_entries: int = 100
    max_error_backups: int = 20
    max_cache_entries: int = 30

    # Auto-continue
    max_continuations: int = 3

    # Notifications
    min_notify_duration: int = 30  # Seconds

    # Stats flushing
    stats_flush_interval: int = 10  # Flush to disk every N tool calls

    # Smart permissions
    permission_approval_threshold: int = 3  # Auto-approve after N approvals

    # Tool success tracker
    tool_failure_threshold: int = 2  # Suggest alternative after N failures

    # Backwards compatibility: UPPER_CASE aliases
    @property
    def OUTPUT_WARNING(self) -> int:
        return self.output_warning

    @property
    def OUTPUT_CRITICAL(self) -> int:
        return self.output_critical

    @property
    def TOKEN_WARNING(self) -> int:
        return self.token_warning

    @property
    def TOKEN_CRITICAL(self) -> int:
        return self.token_critical

    @property
    def DAILY_TOKEN_WARNING(self) -> int:
        return self.daily_token_warning

    @property
    def CHARS_PER_TOKEN(self) -> int:
        return self.chars_per_token

    @property
    def MAX_READS_TRACKED(self) -> int:
        return self.max_reads_tracked

    @property
    def MAX_SEARCHES_TRACKED(self) -> int:
        return self.max_searches_tracked

    @property
    def STALE_MESSAGE_THRESHOLD(self) -> int:
        return self.stale_message_threshold

    @property
    def SIMILARITY_THRESHOLD(self) -> float:
        return self.similarity_threshold

    @property
    def LARGE_FILE_LINES(self) -> int:
        return self.large_file_lines

    @property
    def LARGE_FILE_BYTES(self) -> int:
        return self.large_file_bytes

    @property
    def BATCH_SIMILARITY_THRESHOLD(self) -> int:
        return self.batch_similarity_threshold

    @property
    def TDD_WARNING_THRESHOLD(self) -> int:
        return self.tdd_warning_threshold

    @property
    def MIN_LINES_FOR_TDD(self) -> int:
        return self.min_lines_for_tdd

    @property
    def MAX_REFLEXION_ENTRIES(self) -> int:
        return self.max_reflexion_entries

    @property
    def MAX_ERROR_BACKUPS(self) -> int:
        return self.max_error_backups

    @property
    def MAX_CACHE_ENTRIES(self) -> int:
        return self.max_cache_entries

    @property
    def MAX_CONTINUATIONS(self) -> int:
        return self.max_continuations

    @property
    def MIN_NOTIFY_DURATION(self) -> int:
        return self.min_notify_duration

    @property
    def STATS_FLUSH_INTERVAL(self) -> int:
        return self.stats_flush_interval

    @property
    def PERMISSION_APPROVAL_THRESHOLD(self) -> int:
        return self.permission_approval_threshold

    @property
    def TOOL_FAILURE_THRESHOLD(self) -> int:
        return self.tool_failure_threshold


# Create singleton instance with same name for backwards compatibility
Thresholds = ThresholdConfig()


# =============================================================================
# File Patterns
# =============================================================================

@dataclass(frozen=True)
class FilePatternConfig:
    """File extension and path patterns."""
    # Code file extensions (for TDD guard)
    code_extensions: frozenset = frozenset({'.py', '.js', '.ts', '.jsx', '.tsx', '.go', '.rs', '.java', '.rb'})

    # Test file patterns
    test_patterns: tuple = ('test_', '_test', '.test.', '.spec.', 'tests/', 'test/', '__tests__/')

    # Files to skip for TDD
    tdd_skip_patterns: tuple = (
        '__init__.py', 'conftest.py', 'setup.py', 'pyproject.toml',
        'package.json', 'tsconfig.json', 'Makefile', '.gitignore'
    )

    # Large file handling
    always_summarize: frozenset = frozenset({'.log', '.csv', '.json', '.xml', '.yaml', '.yml'})
    skip_summarize: frozenset = frozenset({'.md', '.txt', '.ini', '.cfg', '.env'})

    # Large output tools (expect big responses)
    large_output_tools: tuple = ("Task", "WebFetch", "WebSearch")

    # Backwards compatibility: UPPER_CASE aliases
    @property
    def CODE_EXTENSIONS(self) -> frozenset:
        return self.code_extensions

    @property
    def TEST_PATTERNS(self) -> tuple:
        return self.test_patterns

    @property
    def TDD_SKIP_PATTERNS(self) -> tuple:
        return self.tdd_skip_patterns

    @property
    def ALWAYS_SUMMARIZE(self) -> frozenset:
        return self.always_summarize

    @property
    def SKIP_SUMMARIZE(self) -> frozenset:
        return self.skip_summarize

    @property
    def LARGE_OUTPUT_TOOLS(self) -> tuple:
        return self.large_output_tools


# Create singleton instance with same name for backwards compatibility
FilePatterns = FilePatternConfig()


# =============================================================================
# Protected Files
# =============================================================================

class ProtectedFiles:
    """File protection patterns."""
    # Read/write blocked
    PROTECTED_PATTERNS = [
        r"\.env$", r"\.env\.[^/]+$",
        r"/\.aws/", r"/\.ssh/",
        r"id_rsa", r"id_ed25519", r"\.pem$",
        r"secrets\.ya?ml$", r"credentials\.json$",
        r"/\.gnupg/",
    ]

    # Write-only blocked (can read, can't write)
    WRITE_ONLY_PATTERNS = [
        r"package-lock\.json$",
        r"yarn\.lock$",
        r"pnpm-lock\.yaml$",
        r"Cargo\.lock$",
        r"poetry\.lock$",
    ]

    # Allowed overrides
    ALLOWED_PATHS = [
        r"\.env\.example$",
        r"\.env\.sample$",
        r"\.env\.template$",
    ]


# =============================================================================
# Dangerous Commands
# =============================================================================

class DangerousCommands:
    """Dangerous command patterns."""
    # (pattern, reason) tuples - will be compiled to regex
    BLOCKED_PATTERNS_RAW = [
        (r"rm\s+-rf?\s+[/~]", "Recursive delete from root or home"),
        (r"rm\s+-rf?\s+\*", "Recursive delete with wildcard"),
        (r":\s*\(\s*\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:", "Fork bomb"),
        (r">\s*/dev/sd[a-z]", "Direct disk write"),
        (r"mkfs\.", "Filesystem format"),
        (r"dd\s+.*of=/dev/", "Direct disk write with dd"),
        (r"chmod\s+-R\s+777\s+/", "Recursive 777 chmod from root"),
        (r"curl.*\|\s*sh", "Piping curl to shell"),
        (r"wget.*\|\s*sh", "Piping wget to shell"),
        (r"eval\s*\$\(curl", "Eval of remote content"),
    ]

    WARNING_PATTERNS_RAW = [
        (r"rm\s+-rf", "Recursive force delete"),
        (r"git\s+push.*--force", "Force push"),
        (r"git\s+reset\s+--hard", "Hard reset"),
        (r"DROP\s+(TABLE|DATABASE)", "SQL DROP statement"),
        (r"TRUNCATE\s+TABLE", "SQL TRUNCATE statement"),
    ]

    @staticmethod
    def get_blocked():
        return _compile_blocked_patterns()

    @staticmethod
    def get_warnings():
        return _compile_warning_patterns()


# =============================================================================
# State Saver Patterns
# =============================================================================

class StateSaver:
    """Patterns for checkpoint state saving."""
    RISKY_PATTERNS_RAW = [
        r'rm\s+-rf?\s+',
        r'git\s+(reset|revert|checkout)\s+--hard',
        r'DROP\s+(TABLE|DATABASE)',
        r'TRUNCATE\s+TABLE',
        r'DELETE\s+FROM.*WHERE\s+1\s*=\s*1',
        r'>\s+[^|]+$',  # Redirect that overwrites
    ]

    RISKY_KEYWORDS = ['delete', 'remove', 'drop', 'truncate', 'reset', 'destroy']

    @staticmethod
    def get_patterns():
        return _compile_state_saver_patterns()


# =============================================================================
# Auto-Continue Patterns
# =============================================================================

class AutoContinue:
    """Patterns for auto-continue detection."""
    INCOMPLETE_PATTERNS_RAW = [
        r"running out of context",
        r"continue\s+in\s+next\s+(message|response)",
        r"will\s+continue",
        r"to\s+be\s+continued",
        r"incomplete",
        r"more\s+to\s+(do|complete)",
        r"remaining\s+(tasks?|items?|steps?)",
        r"\[?TODO\]?.*remaining",
        r"next\s+step[s]?\s*:",
    ]

    COMPLETE_PATTERNS_RAW = [
        r"(all|everything).*(done|complete|finished)",
        r"successfully\s+(completed|finished)",
        r"no\s+(more|remaining)\s+(tasks?|items?|work)",
        r"that'?s\s+(all|it|everything)",
    ]

    # Backwards compatibility - keep original names
    INCOMPLETE_PATTERNS = INCOMPLETE_PATTERNS_RAW
    COMPLETE_PATTERNS = COMPLETE_PATTERNS_RAW

    @staticmethod
    def get_incomplete():
        """Get compiled incomplete patterns."""
        return _compile_incomplete_patterns()

    @staticmethod
    def get_complete():
        """Get compiled complete patterns."""
        return _compile_complete_patterns()


# =============================================================================
# Smart Permission Patterns
# =============================================================================

class SmartPermissions:
    """Auto-approval patterns for smart permissions."""
    # Read patterns (safe file types)
    READ_PATTERNS_RAW = [
        r'\.md$', r'\.txt$', r'\.rst$',
        r'README', r'LICENSE', r'CHANGELOG', r'CONTRIBUTING',
        r'\.json$', r'\.yaml$', r'\.yml$', r'\.toml$', r'\.ini$', r'\.cfg$',
        r'test[_/]', r'_test\.', r'\.test\.', r'\.spec\.', r'__tests__/', r'tests/',
        r'\.d\.ts$', r'\.pyi$',
        r'package-lock\.json$', r'yarn\.lock$', r'pnpm-lock\.yaml$',
        r'Cargo\.lock$', r'poetry\.lock$', r'Pipfile\.lock$',
    ]

    # Write patterns (test files only)
    WRITE_PATTERNS_RAW = [
        r'test[_/]', r'_test\.', r'\.test\.', r'\.spec\.',
        r'__tests__/', r'tests/', r'fixtures/', r'mocks/', r'__mocks__/',
    ]

    # Never auto-approve (sensitive files)
    NEVER_PATTERNS_RAW = [
        r'\.env', r'secrets?', r'credentials?', r'password',
        r'\.pem$', r'\.key$', r'id_rsa', r'\.ssh/', r'\.aws/', r'\.git/',
    ]

    @staticmethod
    def get_read():
        """Get compiled read auto-approve patterns."""
        return _compile_read_permissions_patterns()

    @staticmethod
    def get_write():
        """Get compiled write auto-approve patterns."""
        return _compile_write_permissions_patterns()

    @staticmethod
    def get_never():
        """Get compiled never-approve patterns."""
        return _compile_never_permissions_patterns()


# =============================================================================
# Credential Scanner Patterns
# =============================================================================

@dataclass(frozen=True)
class CredentialConfig:
    """Credential scanner patterns for detecting secrets."""
    sensitive_patterns: tuple[tuple[str, str], ...] = (('(?i)(api[_-]?key|apikey)\\s*[=:]\\s*["\\\']?[a-zA-Z0-9_-]{20,}', 'API key'), ('(?i)(secret[_-]?key|secretkey)\\s*[=:]\\s*["\\\']?[a-zA-Z0-9_-]{20,}', 'Secret key'), ('(?i)(access[_-]?token|accesstoken)\\s*[=:]\\s*["\\\']?[a-zA-Z0-9_-]{20,}', 'Access token'), ('(?i)(auth[_-]?token|authtoken)\\s*[=:]\\s*["\\\']?[a-zA-Z0-9_-]{20,}', 'Auth token'), ('AKIA[0-9A-Z]{16}', 'AWS Access Key ID'), ('(?i)aws[_-]?secret[_-]?access[_-]?key\\s*[=:]\\s*["\\\']?[A-Za-z0-9/+=]{40}', 'AWS Secret Key'), ('-----BEGIN (RSA |DSA |EC |OPENSSH |PGP )?PRIVATE KEY-----', 'Private key'), ('-----BEGIN CERTIFICATE-----', 'Certificate'), ('sk-[a-zA-Z0-9]{48}', 'OpenAI API key'), ('sk-ant-[a-zA-Z0-9\\-_]{90,}', 'Anthropic API key'), ('AIza[0-9A-Za-z\\-_]{35}', 'Google API key'), ('ghp_[a-zA-Z0-9]{36}', 'GitHub PAT'), ('gho_[a-zA-Z0-9]{36}', 'GitHub OAuth token'), ('ghs_[a-zA-Z0-9]{36}', 'GitHub App token'), ('ghu_[a-zA-Z0-9]{36}', 'GitHub user-to-server token'), ('glpat-[a-zA-Z0-9\\-_]{20,}', 'GitLab PAT'), ('xox[baprs]-[a-zA-Z0-9-]+', 'Slack token'), ('sk_live_[a-zA-Z0-9]{24,}', 'Stripe secret key'), ('rk_live_[a-zA-Z0-9]{24,}', 'Stripe restricted key'), ('sq0csp-[a-zA-Z0-9\\-_]{43}', 'Square access token'), ('sq0atp-[a-zA-Z0-9\\-_]{22}', 'Square OAuth token'), ('[MN][a-zA-Z0-9]{23,26}\\.[a-zA-Z0-9]{6}\\.[a-zA-Z0-9_-]{27}', 'Discord bot token'), ('\\d{17,19}:[a-zA-Z0-9_-]{35}', 'Telegram bot token'), ('SG\\.[a-zA-Z0-9_-]{22}\\.[a-zA-Z0-9_-]{43}', 'SendGrid API key'), ('key-[a-zA-Z0-9]{32}', 'Mailgun API key'), ('npm_[a-zA-Z0-9]{36}', 'npm access token'), ('pypi-[a-zA-Z0-9_-]{80,}', 'PyPI API token'), ('rubygems_[a-zA-Z0-9]{48}', 'RubyGems API key'), ('travis-[a-zA-Z0-9]{22}', 'Travis CI token'), ('circle-token-[a-zA-Z0-9]{40}', 'CircleCI token'), ('dop_v1_[a-zA-Z0-9]{64}', 'DigitalOcean PAT'), ('hf_[a-zA-Z0-9]{34,}', 'HuggingFace token'), ('FLWSECK_TEST-[a-zA-Z0-9]{32}', 'Flutterwave secret key'), ('whsec_[a-zA-Z0-9]{32,}', 'Webhook secret'), ('DefaultEndpointsProtocol=https.*AccountKey=[A-Za-z0-9+/=]+', 'Azure connection string'), ('(?i)azure[_-]?storage[_-]?key\\s*[=:]\\s*["\\\']?[A-Za-z0-9+/=]{80,}', 'Azure storage key'), ('(mysql|postgresql|postgres|mongodb|redis|amqp)://[^:]+:[^@]+@', 'Database URI with password'), ('(mssql|sqlserver)://[^:]+:[^@]+@', 'SQL Server URI with password'), ('mongodb\\+srv://[^:]+:[^@]+@', 'MongoDB SRV URI with password'), ('(?i)password\\s*[=:]\\s*["\\\'][^"\\\']{8,}["\\\']', 'Hardcoded password'), ('(?i)passwd\\s*[=:]\\s*["\\\'][^"\\\']{8,}["\\\']', 'Hardcoded password'), ('eyJ[a-zA-Z0-9_-]*\\.eyJ[a-zA-Z0-9_-]*\\.[a-zA-Z0-9_-]*', 'JWT token'))

    allowlist_patterns: tuple[str, ...] = ('.example', '.sample', '.template', 'test', 'mock', 'fake', 'dummy')

    @staticmethod
    def get_compiled_patterns():
        """Get compiled sensitive credential patterns."""
        return _compile_credential_patterns()


# Create singleton instance with same name for backwards compatibility
Credentials = CredentialConfig()


# =============================================================================
# Build Analyzer Configuration
# =============================================================================

@dataclass(frozen=True)
class BuildConfig:
    """Build analyzer patterns and suggestions."""

    BUILD_COMMANDS_RAW: tuple = (
        r"^make\b", r"^cmake\b", r"^ninja\b", r"^meson\b",
        r"^cargo\s+(build|test|check|run)", r"^rustc\b",
        r"^gcc\b", r"^g\+\+\b", r"^clang\b", r"^clang\+\+\b",
        r"^npm\s+(run\s+)?(build|test|start)", r"^yarn\s+(build|test)",
        r"^pnpm\s+(build|test)", r"^bun\s+(build|test)",
        r"^go\s+(build|test|run)", r"^mvn\b", r"^gradle\b",
        r"^python.*setup\.py", r"^pip\s+install",
        r"^pytest\b", r"^python\s+-m\s+pytest",
    )

    ERROR_PATTERNS_RAW: dict = None  # Set in __post_init__

    FIX_SUGGESTIONS: dict = None  # Set in __post_init__

    def __post_init__(self):
        error_patterns = {
            "gcc_clang": [
                (r"error:\s*(.+)", "compile"),
                (r"undefined reference to", "linker"),
                (r"cannot find -l", "linker"),
                (r"fatal error:\s*(.+\.h)", "header"),
            ],
            "rust": [
                (r"error\[E\d+\]:\s*(.+)", "compile"),
                (r"cannot find", "import"),
            ],
            "typescript": [
                (r"error TS\d+:\s*(.+)", "compile"),
                (r"Cannot find module", "import"),
            ],
            "python": [
                (r"ModuleNotFoundError:\s*(.+)", "import"),
                (r"ImportError:\s*(.+)", "import"),
                (r"SyntaxError:\s*(.+)", "syntax"),
            ],
            "go": [
                (r"cannot find package", "import"),
                (r"undefined:\s*(.+)", "compile"),
            ],
            "npm": [
                (r"npm ERR!", "npm"),
                (r"ENOENT", "file"),
            ],
            "make": [
                (r"make:\s*\*\*\*\s*(.+)", "make"),
                (r"No rule to make target", "make"),
            ],
        }
        object.__setattr__(self, 'ERROR_PATTERNS_RAW', error_patterns)

        fix_suggestions = {
            "missing_module": "Check imports and install missing packages",
            "undefined_reference": "Check function declarations and library linking",
            "syntax_error": "Review recent changes for syntax issues",
            "type_error": "Check type annotations and function signatures",
            "permission_denied": "Check file permissions",
            "file_not_found": "Verify file paths exist",
            "network_error": "Check network connectivity",
            "memory_error": "Consider reducing memory usage or increasing limits",
            "timeout": "Consider optimizing or increasing timeout",
            "test_failure": "Review failing test assertions",
            "lint_error": "Run linter and fix style issues",
            "dependency_conflict": "Check package versions for compatibility",
        }
        object.__setattr__(self, 'FIX_SUGGESTIONS', fix_suggestions)

    @staticmethod
    def get_build_commands():
        """Get compiled build command patterns."""
        return _compile_build_commands()

    @staticmethod
    def get_error_patterns():
        """Get compiled error patterns by tool."""
        return _compile_error_patterns()


# Create singleton instance
Build = BuildConfig()


# =============================================================================
# State Limits (centralized magic numbers)
# =============================================================================

@dataclass(frozen=True)
class LimitConfig:
    """Size limits for state management."""
    max_suggested_skills: int = 100
    max_recent_patterns: int = 10
    max_fuzzy_search_entries: int = 30
    max_checkpoints: int = 20
    max_seen_sessions: int = 100
    max_backups: int = 20
    max_chain_recommendations: int = 2
    max_messages_joined: int = 3
    patterns_cache_maxsize: int = 1  # Single entry for learned patterns cache
    hierarchy_cache_maxsize: int = 256  # LRU cache for hierarchy lookups
    content_truncate_summary: int = 500
    content_truncate_cache: int = 2000
    content_truncate_full: int = 10000
    prompt_truncate: int = 100
    command_truncate: int = 500
    url_truncate: int = 80
    daily_stats_cache_maxsize: int = 1  # Single entry for daily stats cache
    token_cache_maxsize: int = 10  # Token cache (context monitor)

    # Backwards compatibility: UPPER_CASE aliases
    @property
    def MAX_SUGGESTED_SKILLS(self) -> int:
        return self.max_suggested_skills

    @property
    def MAX_RECENT_PATTERNS(self) -> int:
        return self.max_recent_patterns

    @property
    def MAX_FUZZY_SEARCH_ENTRIES(self) -> int:
        return self.max_fuzzy_search_entries

    @property
    def MAX_CHECKPOINTS(self) -> int:
        return self.max_checkpoints

    @property
    def MAX_SEEN_SESSIONS(self) -> int:
        return self.max_seen_sessions

    @property
    def MAX_BACKUPS(self) -> int:
        return self.max_backups

    @property
    def MAX_CHAIN_RECOMMENDATIONS(self) -> int:
        return self.max_chain_recommendations

    @property
    def MAX_MESSAGES_JOINED(self) -> int:
        return self.max_messages_joined

    @property
    def CONTENT_TRUNCATE_SUMMARY(self) -> int:
        return self.content_truncate_summary

    @property
    def CONTENT_TRUNCATE_CACHE(self) -> int:
        return self.content_truncate_cache

    @property
    def CONTENT_TRUNCATE_FULL(self) -> int:
        return self.content_truncate_full

    @property
    def PATTERNS_CACHE_MAXSIZE(self) -> int:
        return self.patterns_cache_maxsize

    @property
    def HIERARCHY_CACHE_MAXSIZE(self) -> int:
        return self.hierarchy_cache_maxsize

    @property
    def PROMPT_TRUNCATE(self) -> int:
        return self.prompt_truncate

    @property
    def COMMAND_TRUNCATE(self) -> int:
        return self.command_truncate

    @property
    def URL_TRUNCATE(self) -> int:
        return self.url_truncate

    @property
    def DAILY_STATS_CACHE_MAXSIZE(self) -> int:
        return self.daily_stats_cache_maxsize

    @property
    def TOKEN_CACHE_MAXSIZE(self) -> int:
        return self.token_cache_maxsize


# Create singleton instance with same name for backwards compatibility
Limits = LimitConfig()


# =============================================================================
# JSON Serialization (msgspec for 10x faster parsing)
# =============================================================================

import msgspec

_decoder = msgspec.json.Decoder()
_encoder = msgspec.json.Encoder()


def fast_json_loads(data: bytes | str) -> dict:
    """Fast JSON decode using msgspec."""
    if isinstance(data, str):
        data = data.encode()
    return _decoder.decode(data)


def fast_json_dumps(obj: dict) -> bytes:
    """Fast JSON encode using msgspec."""
    return _encoder.encode(obj)


# =============================================================================
# Compiled Pattern Cache (using lru_cache for thread safety)
# =============================================================================

@lru_cache(maxsize=1)
def _compile_blocked_patterns():
    """Compile blocked dangerous command patterns."""
    return [
        (re.compile(p, re.IGNORECASE), r)
        for p, r in DangerousCommands.BLOCKED_PATTERNS_RAW
    ]


@lru_cache(maxsize=1)
def _compile_warning_patterns():
    """Compile warning dangerous command patterns."""
    return [
        (re.compile(p, re.IGNORECASE), r)
        for p, r in DangerousCommands.WARNING_PATTERNS_RAW
    ]


@lru_cache(maxsize=1)
def _compile_state_saver_patterns():
    """Compile risky state saver patterns."""
    return [
        re.compile(p, re.IGNORECASE)
        for p in StateSaver.RISKY_PATTERNS_RAW
    ]


@lru_cache(maxsize=1)
def _compile_incomplete_patterns():
    """Compile incomplete auto-continue patterns."""
    return [
        re.compile(p, re.IGNORECASE)
        for p in AutoContinue.INCOMPLETE_PATTERNS_RAW
    ]


@lru_cache(maxsize=1)
def _compile_complete_patterns():
    """Compile complete auto-continue patterns."""
    return [
        re.compile(p, re.IGNORECASE)
        for p in AutoContinue.COMPLETE_PATTERNS_RAW
    ]


@lru_cache(maxsize=1)
def _compile_read_permissions_patterns():
    """Compile read auto-approval patterns."""
    return [
        re.compile(p, re.IGNORECASE)
        for p in SmartPermissions.READ_PATTERNS_RAW
    ]


@lru_cache(maxsize=1)
def _compile_write_permissions_patterns():
    """Compile write auto-approval patterns."""
    return [
        re.compile(p, re.IGNORECASE)
        for p in SmartPermissions.WRITE_PATTERNS_RAW
    ]


@lru_cache(maxsize=1)
def _compile_never_permissions_patterns():
    """Compile never-approve patterns."""
    return [
        re.compile(p, re.IGNORECASE)
        for p in SmartPermissions.NEVER_PATTERNS_RAW
    ]


@lru_cache(maxsize=1)
def _compile_credential_patterns():
    """Compile credential scanner patterns."""
    return [
        (re.compile(p), n)
        for p, n in Credentials.sensitive_patterns
    ]


@lru_cache(maxsize=1)
def get_protected_patterns_compiled():
    """Get compiled protected file patterns."""
    return [re.compile(p) for p in ProtectedFiles.PROTECTED_PATTERNS]


@lru_cache(maxsize=1)
def get_write_only_patterns_compiled():
    """Get compiled write-only patterns."""
    return [re.compile(p) for p in ProtectedFiles.WRITE_ONLY_PATTERNS]


@lru_cache(maxsize=1)
def get_allowed_patterns_compiled():
    """Get compiled allowed override patterns."""
    return [re.compile(p) for p in ProtectedFiles.ALLOWED_PATHS]


@lru_cache(maxsize=1)
def _compile_build_commands():
    """Compile build command patterns."""
    return [re.compile(p, re.IGNORECASE) for p in Build.BUILD_COMMANDS_RAW]


@lru_cache(maxsize=1)
def _compile_error_patterns():
    """Compile error patterns by tool."""
    result = {}
    for tool, patterns in Build.ERROR_PATTERNS_RAW.items():
        result[tool] = [(re.compile(p), cat) for p, cat in patterns]
    return result

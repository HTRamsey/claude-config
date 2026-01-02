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
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Sequence


# =============================================================================
# Tool Names - Canonical tool identifiers to reduce typos and enable IDE completion
# =============================================================================

class ToolName(str, Enum):
    """Claude Code tool names as string enum for type safety."""
    # File operations
    READ = "Read"
    EDIT = "Edit"
    WRITE = "Write"
    GLOB = "Glob"
    GREP = "Grep"
    # Execution
    BASH = "Bash"
    TASK = "Task"
    SKILL = "Skill"
    # Web
    WEB_FETCH = "WebFetch"
    WEB_SEARCH = "WebSearch"
    # Other
    LSP = "LSP"
    NOTEBOOK_EDIT = "NotebookEdit"
    TODO_WRITE = "TodoWrite"
    ASK_USER = "AskUserQuestion"
    # MCP
    MCP = "mcp"  # Prefix for MCP tools

    def __str__(self) -> str:
        return self.value

    @classmethod
    def is_file_tool(cls, name: str) -> bool:
        """Check if tool is a file operation tool."""
        return name in (cls.READ, cls.EDIT, cls.WRITE, cls.GLOB, cls.GREP)

    @classmethod
    def is_search_tool(cls, name: str) -> bool:
        """Check if tool is a search operation."""
        return name in (cls.GREP, cls.GLOB, cls.WEB_SEARCH)

    @classmethod
    def is_write_tool(cls, name: str) -> bool:
        """Check if tool modifies files."""
        return name in (cls.EDIT, cls.WRITE, cls.NOTEBOOK_EDIT)


# =============================================================================
# Pattern Compilation Factory
# =============================================================================

def _make_pattern_compiler(
    raw_patterns: Sequence,
    flags: int = re.IGNORECASE,
    with_value: bool = False
):
    """Create a cached pattern compiler function.

    Args:
        raw_patterns: List of patterns or (pattern, value) tuples
        flags: Regex flags (default: re.IGNORECASE)
        with_value: If True, expects (pattern, value) tuples

    Returns:
        A cached function that compiles the patterns
    """
    @lru_cache(maxsize=1)
    def compile_patterns():
        if with_value:
            return [(re.compile(p, flags), v) for p, v in raw_patterns]
        return [re.compile(p, flags) for p in raw_patterns]
    return compile_patterns

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

    def __getattr__(self, name: str):
        """Support UPPER_CASE aliases for backwards compatibility."""
        if name.isupper() or ('_' in name and name == name.upper()):
            try:
                return object.__getattribute__(self, name.lower())
            except AttributeError:
                pass
        raise AttributeError(f"'{type(self).__name__}' has no attribute '{name}'")


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
    large_file_lines: int = 500
    large_file_bytes: int = 50000

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

    def __getattr__(self, name: str):
        """Support UPPER_CASE aliases for backwards compatibility."""
        if name.isupper() or ('_' in name and name == name.upper()):
            try:
                return object.__getattribute__(self, name.lower())
            except AttributeError:
                pass
        raise AttributeError(f"'{type(self).__name__}' has no attribute '{name}'")


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

    def __getattr__(self, name: str):
        """Support UPPER_CASE aliases for backwards compatibility."""
        if name.isupper() or ('_' in name and name == name.upper()):
            try:
                return object.__getattribute__(self, name.lower())
            except AttributeError:
                pass
        raise AttributeError(f"'{type(self).__name__}' has no attribute '{name}'")


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
    """Dangerous command patterns.

    Note: These are best-effort guardrails, not security boundaries.
    Determined attackers can bypass regex-based detection.
    """
    # (pattern, reason) tuples - will be compiled to regex
    # Patterns handle: -rf, -fr, -r -f, --recursive --force, etc.
    BLOCKED_PATTERNS_RAW = [
        # rm variants targeting root/home - catches -rf, -fr, -r -f, --recursive, etc.
        (r"rm\s+(-[a-z]*r[a-z]*\s+)*(-[a-z]*f[a-z]*\s+)*[/~]", "Recursive delete from root or home"),
        (r"rm\s+(-[a-z]*f[a-z]*\s+)*(-[a-z]*r[a-z]*\s+)*[/~]", "Recursive delete from root or home"),
        (r"rm\s+--recursive\s+.*[/~]", "Recursive delete from root or home"),
        (r"rm\s+--force\s+--recursive\s+.*[/~]", "Recursive delete from root or home"),
        (r"rm\s+-rf?\s+\*", "Recursive delete with wildcard"),
        (r"rm\s+-fr\s+\*", "Recursive delete with wildcard"),
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
        # Warn on any recursive delete (catches -rf, -fr, -r -f, --recursive)
        (r"rm\s+(-[a-z]*[rf][a-z]*\s*)+", "Recursive or force delete"),
        (r"rm\s+--recursive", "Recursive delete"),
        (r"rm\s+--force", "Force delete"),
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
# Tool Analytics Configuration
# =============================================================================

@dataclass(frozen=True)
class ToolAnalyticsConfig:
    """Error patterns and alternatives for tool failure detection."""

    # Error patterns with suggestions for tool_analytics handler
    ERROR_PATTERNS_RAW: dict = None  # Set in __post_init__

    # Tool alternatives for repeated failures
    TOOL_ALTERNATIVES: dict = None  # Set in __post_init__

    def __post_init__(self):
        error_patterns = {
            r"old_string.*not found|not unique|no match": {
                "tool": "Edit",
                "suggestion": "Re-read the file to get current content, or use Read tool first",
                "action": "read_first"
            },
            r"file.*not found|no such file": {
                "tool": "*",
                "suggestion": "Check file path with: smart-find.sh <pattern> .",
                "action": "find_file"
            },
            r"permission denied|access denied|not permitted": {
                "tool": "*",
                "suggestion": "Check file permissions or try Task(subagent_type=Explore) for read-only exploration",
                "action": "check_perms"
            },
            r"no matches|no results|pattern not found": {
                "tool": "Grep",
                "suggestion": "Try broader pattern or use Task(subagent_type=Explore) for fuzzy search",
                "action": "broaden_search"
            },
            r"build failed|compilation error|make.*error": {
                "tool": "Bash",
                "suggestion": "Pipe through compress.sh --type build to focus on errors",
                "action": "compress_output"
            },
            r"test.*failed|assertion.*error|pytest.*failed": {
                "tool": "Bash",
                "suggestion": "Pipe through compress.sh --type tests to focus on failures",
                "action": "compress_output"
            },
            r"conflict|merge.*failed|rebase.*failed": {
                "tool": "Bash",
                "suggestion": "Use smart-diff.sh to understand conflicts",
                "action": "use_diff"
            },
            r"timeout|timed out|killed": {
                "tool": "*",
                "suggestion": "Command too slow - try limiting scope or using more specific patterns",
                "action": "reduce_scope"
            },
        }
        object.__setattr__(self, 'ERROR_PATTERNS_RAW', error_patterns)

        tool_alternatives = {
            "Grep": "Consider Task(subagent_type=Explore) for complex searches",
            "Glob": "Try smart-find.sh with fd for faster, .gitignore-aware search",
            "Read": "For large files, use smart-view.sh",
            "Edit": "If edits keep failing, re-read file or check for concurrent modifications",
            "Bash": "For build/test commands, pipe through compress-*.sh scripts",
        }
        object.__setattr__(self, 'TOOL_ALTERNATIVES', tool_alternatives)

    @staticmethod
    def get_error_patterns():
        """Get compiled error patterns for tool failure detection."""
        return _compile_tool_analytics_patterns()


# Create singleton instance
ToolAnalytics = ToolAnalyticsConfig()


# =============================================================================
# Suggestion Engine Patterns
# =============================================================================

class SuggestionPatterns:
    """Patterns for suggestion engine (skill suggestions, agent chaining, optimization)."""

    # Skill file patterns for creator suggestions
    SKILL_SUGGESTIONS_RAW = [
        {"pattern": r"\.claude/hooks/.*\.py$", "skill": "hook-creator", "type": "hook"},
        {"pattern": r"\.claude/agents/.*\.md$", "skill": "agent-creator", "type": "agent"},
        {"pattern": r"\.claude/commands/.*\.md$", "skill": "command-creator", "type": "command"},
        {"pattern": r"\.claude/skills/.*/SKILL\.md$", "skill": "skill-creator", "type": "skill"},
    ]

    # Agent recommendations for subagent suggestions
    AGENT_RECOMMENDATIONS = {
        "exploration": ("Explore", "Haiku-powered codebase exploration"),
        "lookup": ("quick-lookup", "Single fact retrieval (Haiku, 10x cheaper)"),
    }

    # Bash command alternatives (pattern -> (script, reason))
    BASH_ALTERNATIVES_RAW = {
        # Offload scripts (huge token savings)
        r"^grep\s": ("offload-grep.sh", "97% token savings"),
        r"^rg\s": ("offload-grep.sh", "97% token savings"),
        r"^find\s": ("offload-find.sh", "95% token savings"),
        r"^find\s.*-name": ("offload-find.sh", "uses fd, 10x faster, respects .gitignore"),

        # Compress scripts (build/test output)
        r"^npm\s+(test|run\s+test)": ("compress.sh --type tests", "pipe output"),
        r"^pytest": ("compress.sh --type tests", "pipe output"),
        r"^make\b": ("compress.sh --type build", "pipe for errors only"),
        r"^cmake\b": ("compress.sh --type build", "pipe for errors only"),
        r"^cat\s.*\.(log|txt)": ("compress.sh --type logs", "errors/warnings only"),

        # Smart viewers (unified file viewing)
        r"^cat\s": ("smart/smart-view.sh", "unified viewer with syntax highlighting"),
        r"^head\s": ("smart/smart-view.sh", "unified viewer with line range"),
        r"^tail\s": ("smart/smart-view.sh", "unified viewer with line range"),

        # Smart AST (structural code search)
        r"^grep.*def\s": ("smart-ast.sh", "uses ast-grep, finds function definitions structurally"),
        r"^grep.*class\s": ("smart-ast.sh", "uses ast-grep, finds class definitions structurally"),
        r"^grep.*function\s": ("smart-ast.sh", "uses ast-grep, finds function definitions structurally"),
        r"^grep.*import\s": ("smart-ast.sh", "uses ast-grep, finds imports structurally"),

        # Smart utilities (modern CLI replacements)
        r"^ls\s+(-la|-l|-a)": ("smart-ls.sh", "uses eza, 87% smaller output"),
        r"^ls\s*$": ("smart-ls.sh", "uses eza, 87% smaller output"),
        r"^tree\s": ("smart-tree.sh", "uses eza --tree, respects .gitignore"),
        r"^du\s": ("smart-du.sh", "uses dust, compact visual output"),
        r"^sed\s": ("smart-replace.sh", "uses sd, simpler syntax"),
        r"^diff\s": ("smart-difft.sh", "uses difftastic, structural diff"),
        r"^git\s+diff": ("smart-diff.sh", "uses delta, 99% savings on large diffs"),
        r"^git\s+blame": ("smart-blame.sh", "filters formatting commits, adds context"),
        r"^(cat|less).*\.json\s*\|\s*jq": ("smart-json.sh", "simpler field extraction syntax"),
    }

    # Agent chaining rules for Task output analysis
    CHAIN_RULES_RAW = [
        {
            "patterns": [
                r"(?i)(sql injection|xss|csrf|command injection|path traversal)",
                r"(?i)(hardcoded (credential|secret|password|api.?key))",
                r"(?i)(authentication|authorization).*(missing|bypass|vulnerable)",
                r"(?i)(insecure|vulnerable).*(crypto|random|hash)",
                r"(?i)🔴.*security",
            ],
            "agent": "code-reviewer",
            "reason": "Security vulnerability detected - deep security analysis recommended",
        },
        {
            "patterns": [
                r"(?i)(n\+1|n \+ 1).*(query|queries)",
                r"(?i)(memory leak|unbounded|allocation in (hot|loop))",
                r"(?i)O\(n[²2]\)|O\(n\^2\)",
                r"(?i)(performance|slow).*(critical|severe|significant)",
                r"(?i)🟡.*performance",
            ],
            "agent": "code-reviewer",
            "reason": "Performance issue detected - code review with performance focus recommended",
        },
        {
            "patterns": [
                r"(?i)(accessibility|a11y|wcag|aria).*(missing|issue|violation)",
                r"(?i)(screen reader|keyboard).*(navigation|focus|trap)",
                r"(?i)\.(jsx|tsx|vue|svelte|qml):\d+",
            ],
            "agent": "code-reviewer",
            "reason": "UI code or accessibility issue - code review with accessibility focus recommended",
        },
        {
            "patterns": [
                r"(?i)(no test|missing test|untested|test coverage).*(low|none|missing)",
                r"(?i)(edge case|boundary|error handling).*(not|missing|untested)",
            ],
            "agent": "test-generator",
            "reason": "Test gaps detected - test generation recommended",
        },
        {
            "patterns": [
                r"(?i)(unused|dead|orphan).*(function|class|import|variable|code)",
                r"(?i)(deprecated|obsolete).*(still|found|exists)",
            ],
            "agent": "code-reviewer",
            "reason": "Potential dead code - code review for cleanup recommended",
        },
    ]

    # Agents that can be chained from Task output
    CHAINABLE_AGENTS = {"code-reviewer", "Explore", "error-explainer", "quick-lookup"}

    @staticmethod
    def get_skill_suggestions():
        """Get compiled skill suggestion patterns."""
        return _compile_skill_suggestions()

    @staticmethod
    def get_bash_alternatives():
        """Get compiled bash command alternatives."""
        return _compile_bash_alternatives()

    @staticmethod
    def get_chain_rules():
        """Get compiled agent chaining rules."""
        return _compile_chain_rules()


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

    def __getattr__(self, name: str):
        """Support UPPER_CASE aliases for backwards compatibility."""
        if name.isupper() or ('_' in name and name == name.upper()):
            try:
                return object.__getattribute__(self, name.lower())
            except AttributeError:
                pass
        raise AttributeError(f"'{type(self).__name__}' has no attribute '{name}'")


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
# Compiled Pattern Cache (using factory for consistency)
# =============================================================================

# Pattern compilers using factory (with_value=True for (pattern, reason) tuples)
_compile_blocked_patterns = _make_pattern_compiler(
    DangerousCommands.BLOCKED_PATTERNS_RAW, with_value=True)
_compile_warning_patterns = _make_pattern_compiler(
    DangerousCommands.WARNING_PATTERNS_RAW, with_value=True)

# Simple pattern lists (IGNORECASE is default)
_compile_state_saver_patterns = _make_pattern_compiler(StateSaver.RISKY_PATTERNS_RAW)
_compile_incomplete_patterns = _make_pattern_compiler(AutoContinue.INCOMPLETE_PATTERNS_RAW)
_compile_complete_patterns = _make_pattern_compiler(AutoContinue.COMPLETE_PATTERNS_RAW)
_compile_read_permissions_patterns = _make_pattern_compiler(SmartPermissions.READ_PATTERNS_RAW)
_compile_write_permissions_patterns = _make_pattern_compiler(SmartPermissions.WRITE_PATTERNS_RAW)
_compile_never_permissions_patterns = _make_pattern_compiler(SmartPermissions.NEVER_PATTERNS_RAW)
_compile_build_commands = _make_pattern_compiler(Build.BUILD_COMMANDS_RAW)

# Credential patterns (no IGNORECASE, with name tuples)
_compile_credential_patterns = _make_pattern_compiler(
    Credentials.sensitive_patterns, flags=0, with_value=True)

# Protected file patterns (no IGNORECASE)
get_protected_patterns_compiled = _make_pattern_compiler(
    ProtectedFiles.PROTECTED_PATTERNS, flags=0)
get_write_only_patterns_compiled = _make_pattern_compiler(
    ProtectedFiles.WRITE_ONLY_PATTERNS, flags=0)
get_allowed_patterns_compiled = _make_pattern_compiler(
    ProtectedFiles.ALLOWED_PATHS, flags=0)


@lru_cache(maxsize=1)
def _compile_error_patterns():
    """Compile error patterns by tool (dict structure, kept as-is)."""
    return {
        tool: [(re.compile(p), cat) for p, cat in patterns]
        for tool, patterns in Build.ERROR_PATTERNS_RAW.items()
    }


@lru_cache(maxsize=1)
def _compile_tool_analytics_patterns():
    """Compile tool analytics error patterns."""
    return [(re.compile(p, re.IGNORECASE), info)
            for p, info in ToolAnalytics.ERROR_PATTERNS_RAW.items()]


# =============================================================================
# Suggestion Engine Pattern Compilers
# =============================================================================

@lru_cache(maxsize=1)
def _compile_skill_suggestions():
    """Compile skill suggestion patterns."""
    return [
        {"pattern": re.compile(s["pattern"]), "skill": s["skill"], "type": s["type"]}
        for s in SuggestionPatterns.SKILL_SUGGESTIONS_RAW
    ]


@lru_cache(maxsize=1)
def _compile_bash_alternatives():
    """Compile bash alternative patterns."""
    return [
        (re.compile(p, re.IGNORECASE), alt, reason)
        for p, (alt, reason) in SuggestionPatterns.BASH_ALTERNATIVES_RAW.items()
    ]


@lru_cache(maxsize=1)
def _compile_chain_rules():
    """Compile agent chaining rules."""
    return [
        {
            "patterns": [re.compile(p) for p in rule["patterns"]],
            "agent": rule["agent"],
            "reason": rule["reason"],
        }
        for rule in SuggestionPatterns.CHAIN_RULES_RAW
    ]

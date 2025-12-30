"""
Centralized configuration for Claude Code hooks.

All configurable constants in one place for easy tuning.
Individual hooks import from here for consistency.

Categories:
- Paths: Data directories and file locations
- Timeouts: TTLs, intervals, and durations
- Thresholds: Limits and warning levels
- Patterns: File extensions, regex patterns
"""
import os
import re
from pathlib import Path

# =============================================================================
# Paths
# =============================================================================

DATA_DIR = Path(os.environ.get("CLAUDE_DATA_DIR", Path.home() / ".claude/data"))
CACHE_DIR = DATA_DIR / "cache"
TRACKER_DIR = Path(os.environ.get("CLAUDE_TRACKER_DIR", DATA_DIR / "tracking"))

# State files
STATE_FILES = {
    "checkpoint": DATA_DIR / "checkpoint-state.json",
    "auto_continue": DATA_DIR / "auto-continue-state.json",
    "reflexion": DATA_DIR / "reflexion-log.json",
    "permission_patterns": DATA_DIR / "permission-patterns.json",
    "usage_stats": DATA_DIR / "usage-stats.json",
    "hook_config": DATA_DIR / "hook-config.json",
    "hook_events": DATA_DIR / "hook-events.jsonl",
}

# =============================================================================
# Timeouts and Intervals (seconds)
# =============================================================================

class Timeouts:
    """Timeout and interval settings."""
    # Handler execution
    HANDLER_TIMEOUT_MS = int(os.environ.get("HANDLER_TIMEOUT", "1000"))
    HANDLER_TIMEOUT_S = HANDLER_TIMEOUT_MS / 1000.0

    # Cache TTLs
    CACHE_TTL = 5  # In-memory cache TTL
    HIERARCHY_CACHE_TTL = 5.0  # Hierarchical rules cache
    EXPLORATION_CACHE_TTL = 3600  # 1 hour for exploration results
    RESEARCH_CACHE_TTL = 86400  # 24 hours for web research

    # State management
    STATE_MAX_AGE = 86400  # Clear state after 24 hours
    CHECKPOINT_INTERVAL = 300  # Min seconds between checkpoints
    CLEANUP_INTERVAL = 300  # Rate-limit cleanup operations

    # TDD guard
    WARNING_WINDOW = 3600  # 1 hour window for counting TDD warnings

    # Auto-continue
    CONTINUE_WINDOW = 300  # 5 minutes

    # Stale context
    STALE_TIME_THRESHOLD = 300  # 5 minutes


# =============================================================================
# Thresholds and Limits
# =============================================================================

class Thresholds:
    """Warning thresholds and limits."""
    # Token/output warnings
    OUTPUT_WARNING = 10000  # Warn if output > 10K chars
    OUTPUT_CRITICAL = 50000  # Strong warning if > 50K chars
    TOKEN_WARNING = 40000  # Warn at 40K tokens
    TOKEN_CRITICAL = 80000  # Strong warning at 80K
    DAILY_TOKEN_WARNING = 500000  # Warn at 500K tokens/day
    CHARS_PER_TOKEN = 4  # Rough estimate

    # File monitoring
    MAX_READS_TRACKED = 100
    MAX_SEARCHES_TRACKED = 50
    STALE_MESSAGE_THRESHOLD = 15  # Warn if read >15 messages ago
    SIMILARITY_THRESHOLD = 0.8  # Fuzzy pattern matching

    # Large file detection
    LARGE_FILE_LINES = 200
    LARGE_FILE_BYTES = 15000

    # Batch detection
    BATCH_SIMILARITY_THRESHOLD = 3  # Suggest after 3 similar ops

    # TDD guard
    TDD_WARNING_THRESHOLD = 3  # Block after this many warnings
    MIN_LINES_FOR_TDD = 30

    # State limits
    MAX_REFLEXION_ENTRIES = 100
    MAX_ERROR_BACKUPS = 20
    MAX_CACHE_ENTRIES = 30

    # Auto-continue
    MAX_CONTINUATIONS = 3

    # Notifications
    MIN_NOTIFY_DURATION = 30  # Seconds

    # Stats flushing
    STATS_FLUSH_INTERVAL = 10  # Flush to disk every N tool calls


# =============================================================================
# File Patterns
# =============================================================================

class FilePatterns:
    """File extension and path patterns."""
    # Code file extensions (for TDD guard)
    CODE_EXTENSIONS = {'.py', '.js', '.ts', '.jsx', '.tsx', '.go', '.rs', '.java', '.rb'}

    # Test file patterns
    TEST_PATTERNS = ['test_', '_test', '.test.', '.spec.', 'tests/', 'test/', '__tests__/']

    # Files to skip for TDD
    TDD_SKIP_PATTERNS = [
        '__init__.py', 'conftest.py', 'setup.py', 'pyproject.toml',
        'package.json', 'tsconfig.json', 'Makefile', '.gitignore'
    ]

    # Large file handling
    ALWAYS_SUMMARIZE = {'.log', '.csv', '.json', '.xml', '.yaml', '.yml'}
    SKIP_SUMMARIZE = {'.md', '.txt', '.ini', '.cfg', '.env'}

    # Large output tools (expect big responses)
    LARGE_OUTPUT_TOOLS = ["Task", "WebFetch", "WebSearch"]


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
    """Dangerous command patterns (compiled on first access)."""
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

    _blocked_compiled = None
    _warning_compiled = None

    @classmethod
    def get_blocked(cls):
        if cls._blocked_compiled is None:
            cls._blocked_compiled = [
                (re.compile(p, re.IGNORECASE), r)
                for p, r in cls.BLOCKED_PATTERNS_RAW
            ]
        return cls._blocked_compiled

    @classmethod
    def get_warnings(cls):
        if cls._warning_compiled is None:
            cls._warning_compiled = [
                (re.compile(p, re.IGNORECASE), r)
                for p, r in cls.WARNING_PATTERNS_RAW
            ]
        return cls._warning_compiled


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

    _patterns_compiled = None

    @classmethod
    def get_patterns(cls):
        if cls._patterns_compiled is None:
            cls._patterns_compiled = [
                re.compile(p, re.IGNORECASE)
                for p in cls.RISKY_PATTERNS_RAW
            ]
        return cls._patterns_compiled


# =============================================================================
# Auto-Continue Patterns
# =============================================================================

class AutoContinue:
    """Patterns for auto-continue detection."""
    INCOMPLETE_PATTERNS = [
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

    COMPLETE_PATTERNS = [
        r"(all|everything).*(done|complete|finished)",
        r"successfully\s+(completed|finished)",
        r"no\s+(more|remaining)\s+(tasks?|items?|work)",
        r"that'?s\s+(all|it|everything)",
    ]

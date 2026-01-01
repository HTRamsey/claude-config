"""
Hook utilities package - modular utilities for Claude Code hooks.

This package provides backwards-compatible imports from the original hook_utils.py.
All original exports are available from this module.

Usage:
    from hooks.hook_utils import log_event, graceful_main, read_state
    # or
    from hooks.hook_utils.logging import log_event
    from hooks.hook_utils.state import read_state
"""

# Re-export everything for backwards compatibility
from .logging import (
    DATA_DIR,
    LOG_FILE,
    ensure_data_dir,
    log_event,
    graceful_main,
    read_stdin_context,
)

from .io import (
    file_lock,
    safe_load_json,
    safe_save_json,
    atomic_write_json,
)

from .state import (
    CACHE_TTL,
    read_state,
    write_state,
    update_state,
    flush_pending_writes,
)

from .session import (
    SESSION_STATE_DIR,
    SESSION_STATE_FILE,
    SESSION_STATE_MAX_AGE,
    get_session_id,
    get_session_state,
    read_session_state,
    write_session_state,
    update_session_state,
    cleanup_old_sessions,
    load_state_with_expiry,
    save_state_with_timestamp,
    backup_transcript,
)

from .hooks import (
    HOOK_DISABLED_TTL,
    is_hook_disabled,
    record_usage,
)

from .io import (
    safe_stat,
    safe_mtime,
    safe_exists,
    normalize_path,
    expand_path,
)

from .metrics import (
    estimate_tokens,
    get_content_size,
    count_tokens_accurate,
    get_timestamp,
)

from .state import (
    TTLCachedLoader,
)

# Note: BlockingHook is in hook_sdk - import directly from there
# Not re-exported here to avoid circular imports

# Note: DAILY_TTL and SESSION_TTL removed - use config.py Timeouts instead

# Event detection utilities - canonical implementations
# These are also available in hook_sdk for the typed context approach
def detect_event(ctx: dict) -> str:
    """
    Detect event type from context dictionary.

    Standardizes event detection across all hooks.

    Returns:
        Event type string: "PreToolUse", "PostToolUse", "SessionStart", etc.
    """
    # PostToolUse has tool_response or tool_result
    if "tool_response" in ctx or "tool_result" in ctx:
        return "PostToolUse"
    # PreCompact has transcript_path but no tool_name
    if "transcript_path" in ctx and not ctx.get("tool_name"):
        return "PreCompact"
    # Explicit event field
    event = ctx.get("event")
    if event in ("SessionStart", "SessionEnd", "Stop", "PermissionRequest",
                 "SubagentStart", "SubagentStop"):
        return event
    # UserPromptSubmit has user_prompt
    if "user_prompt" in ctx:
        return "UserPromptSubmit"
    # PreToolUse has tool_name without tool_response
    if ctx.get("tool_name"):
        return "PreToolUse"
    return "PreToolUse"


def is_post_tool_use(ctx: dict) -> bool:
    """Check if context is from a PostToolUse event."""
    return detect_event(ctx) == "PostToolUse"


def is_pre_tool_use(ctx: dict) -> bool:
    """Check if context is from a PreToolUse event."""
    return detect_event(ctx) == "PreToolUse"


def get_tool_response(ctx: dict, default=None):
    """Get tool response from PostToolUse context."""
    return ctx.get("tool_response") or ctx.get("tool_result") or default


__all__ = [
    # Logging
    "DATA_DIR",
    "LOG_FILE",
    "ensure_data_dir",
    "log_event",
    "graceful_main",
    "read_stdin_context",
    # I/O
    "file_lock",
    "safe_load_json",
    "safe_save_json",
    "atomic_write_json",
    # State
    "CACHE_TTL",
    "read_state",
    "write_state",
    "update_state",
    "flush_pending_writes",
    # Session
    "SESSION_STATE_DIR",
    "SESSION_STATE_FILE",
    "SESSION_STATE_MAX_AGE",
    "get_session_id",
    "get_session_state",
    "read_session_state",
    "write_session_state",
    "update_session_state",
    "cleanup_old_sessions",
    "load_state_with_expiry",
    "save_state_with_timestamp",
    # Hooks
    "HOOK_DISABLED_TTL",
    "is_hook_disabled",
    "record_usage",
    # Session (includes backup)
    "backup_transcript",
    # File Operations & Paths (from io.py)
    "safe_stat",
    "safe_mtime",
    "safe_exists",
    "normalize_path",
    "expand_path",
    # Metrics
    "estimate_tokens",
    "get_content_size",
    "count_tokens_accurate",
    "get_timestamp",
    # State (includes TTLCachedLoader)
    "TTLCachedLoader",
    # Note: BlockingHook is in hook_sdk, not re-exported here
    # Event detection & utilities
    "detect_event",
    "is_post_tool_use",
    "is_pre_tool_use",
    "get_tool_response",
]

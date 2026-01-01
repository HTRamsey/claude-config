#!/home/jonglaser/.claude/data/venv/bin/python3
"""
Claude Code Hook SDK - Typed abstractions for hook development.

Provides:
- Typed context dataclasses (PreToolUseContext, PostToolUseContext, etc.)
- Response builders (allow, deny, message, continue_with_message)
- Common patterns (file matching, command parsing, rate limiting)
- Handler decorators for cleaner hook code

Usage:
    from hook_sdk import (
        PreToolUseContext,
        hook_handler,
        Response,
    )

    @hook_handler("my_hook", event="PreToolUse")
    def handle(ctx: PreToolUseContext) -> Response | None:
        if ctx.tool_name == "Bash":
            return Response.deny("Not allowed")
        return None
"""
import fnmatch
import hashlib
import json
import os
import re
import sys
import threading
import time
from dataclasses import dataclass, field
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Literal

# Import base utilities
from hook_utils import (
    graceful_main,
    log_event,
    read_state,
    write_state,
    read_session_state,
    write_session_state,
    update_session_state,
    cleanup_old_sessions,
    get_session_id,
    DATA_DIR,
)

# Event types
EventType = Literal[
    "PreToolUse",
    "PostToolUse",
    "SessionStart",
    "SessionEnd",
    "UserPromptSubmit",
    "PreCompact",
    "Stop",
    "SubagentStart",
    "SubagentStop",
    "PermissionRequest",
]

# Tool types
ToolType = Literal[
    "Bash", "Read", "Write", "Edit", "Glob", "Grep",
    "Task", "WebFetch", "WebSearch", "LSP", "Skill",
    "TodoWrite", "NotebookEdit", "AskUserQuestion",
]


# =============================================================================
# Event Detection (standardized across all hooks)
# =============================================================================

def detect_event(ctx: dict) -> EventType:
    """
    Detect event type from context dictionary.

    Standardizes event detection across all hooks - use this instead of
    checking individual keys manually.

    Returns:
        EventType string
    """
    # PostToolUse has tool_response or tool_result
    if "tool_response" in ctx or "tool_result" in ctx:
        return "PostToolUse"

    # PreCompact has transcript_path but no tool_name
    if "transcript_path" in ctx and not ctx.get("tool_name"):
        return "PreCompact"

    # SessionStart/SessionEnd
    if ctx.get("event") == "SessionStart":
        return "SessionStart"
    if ctx.get("event") == "SessionEnd":
        return "SessionEnd"

    # UserPromptSubmit has user_prompt
    if "user_prompt" in ctx:
        return "UserPromptSubmit"

    # Stop event
    if ctx.get("event") == "Stop":
        return "Stop"

    # PermissionRequest
    if ctx.get("event") == "PermissionRequest":
        return "PermissionRequest"

    # Subagent events
    if ctx.get("event") == "SubagentStart":
        return "SubagentStart"
    if ctx.get("event") == "SubagentStop":
        return "SubagentStop"

    # PreToolUse has tool_name without tool_response
    if ctx.get("tool_name"):
        return "PreToolUse"

    # Default to PreToolUse for backwards compatibility
    return "PreToolUse"


def is_post_tool_use(ctx: dict) -> bool:
    """Check if context is from a PostToolUse event."""
    return detect_event(ctx) == "PostToolUse"


def is_pre_tool_use(ctx: dict) -> bool:
    """Check if context is from a PreToolUse event."""
    return detect_event(ctx) == "PreToolUse"


def get_tool_response(ctx: dict, default=None) -> Any:
    """Get tool response from PostToolUse context."""
    return ctx.get("tool_response") or ctx.get("tool_result") or default


# =============================================================================
# Context Dataclasses
# =============================================================================

@dataclass
class ToolInput:
    """Parsed tool input with typed accessors."""
    raw: dict = field(default_factory=dict)

    # Common fields
    @property
    def file_path(self) -> str:
        return self.raw.get("file_path", "")

    @property
    def command(self) -> str:
        return self.raw.get("command", "")

    @property
    def pattern(self) -> str:
        return self.raw.get("pattern", "")

    @property
    def content(self) -> str:
        return self.raw.get("content", "")

    @property
    def old_string(self) -> str:
        return self.raw.get("old_string", "")

    @property
    def new_string(self) -> str:
        return self.raw.get("new_string", "")

    @property
    def prompt(self) -> str:
        return self.raw.get("prompt", "")

    @property
    def url(self) -> str:
        return self.raw.get("url", "")

    @property
    def subagent_type(self) -> str:
        return self.raw.get("subagent_type", "")

    @property
    def skill(self) -> str:
        return self.raw.get("skill", "")

    def get(self, key: str, default: Any = None) -> Any:
        return self.raw.get(key, default)


@dataclass
class ToolResult:
    """Parsed tool result with typed accessors."""
    raw: dict = field(default_factory=dict)

    @property
    def exit_code(self) -> int | None:
        code = self.raw.get("exit_code") or self.raw.get("exitCode")
        return int(code) if code is not None else None

    @property
    def stdout(self) -> str:
        return str(self.raw.get("stdout", ""))

    @property
    def stderr(self) -> str:
        return str(self.raw.get("stderr", ""))

    @property
    def output(self) -> str:
        """Combined stdout + stderr."""
        return self.stdout + ("\n" + self.stderr if self.stderr else "")

    @property
    def success(self) -> bool:
        return self.exit_code == 0 if self.exit_code is not None else True

    def get(self, key: str, default: Any = None) -> Any:
        return self.raw.get(key, default)


@dataclass
class BaseContext:
    """Base context with common fields."""
    raw: dict = field(default_factory=dict)

    @property
    def session_id(self) -> str:
        return get_session_id(self.raw)

    @property
    def cwd(self) -> str:
        return self.raw.get("cwd", os.getcwd())

    @property
    def transcript_path(self) -> str:
        return self.raw.get("transcript_path", "")

    def get(self, key: str, default: Any = None) -> Any:
        return self.raw.get(key, default)


@dataclass
class PreToolUseContext(BaseContext):
    """Context for PreToolUse hooks."""

    @property
    def tool_name(self) -> str:
        return self.raw.get("tool_name", "")

    @property
    def tool_input(self) -> ToolInput:
        return ToolInput(self.raw.get("tool_input", {}))

    # Convenience properties
    @property
    def is_bash(self) -> bool:
        return self.tool_name == "Bash"

    @property
    def is_read(self) -> bool:
        return self.tool_name == "Read"

    @property
    def is_write(self) -> bool:
        return self.tool_name == "Write"

    @property
    def is_edit(self) -> bool:
        return self.tool_name == "Edit"

    @property
    def is_file_op(self) -> bool:
        return self.tool_name in ("Read", "Write", "Edit")

    @property
    def is_search(self) -> bool:
        return self.tool_name in ("Grep", "Glob")


@dataclass
class PostToolUseContext(BaseContext):
    """Context for PostToolUse hooks."""

    @property
    def tool_name(self) -> str:
        return self.raw.get("tool_name", "")

    @property
    def tool_input(self) -> ToolInput:
        return ToolInput(self.raw.get("tool_input", {}))

    @property
    def tool_result(self) -> ToolResult:
        # Claude Code uses "tool_response" for PostToolUse hooks
        return ToolResult(self.raw.get("tool_response") or self.raw.get("tool_result", {}))

    @property
    def duration_ms(self) -> int:
        return self.raw.get("duration_ms", 0)

    @property
    def duration_secs(self) -> float:
        return self.duration_ms / 1000.0


@dataclass
class SessionContext(BaseContext):
    """Context for SessionStart/SessionEnd hooks."""

    @property
    def is_resume(self) -> bool:
        return self.raw.get("is_resume", False)


@dataclass
class PromptContext(BaseContext):
    """Context for UserPromptSubmit hooks."""

    @property
    def user_prompt(self) -> str:
        return self.raw.get("user_prompt", "")

    @property
    def token_count(self) -> int:
        return self.raw.get("token_count", 0)


@dataclass
class SubagentContext(BaseContext):
    """Context for SubagentStart/SubagentStop hooks."""

    @property
    def subagent_type(self) -> str:
        return self.raw.get("subagent_type", "")

    @property
    def subagent_id(self) -> str:
        return self.raw.get("subagent_id", "")

    @property
    def prompt(self) -> str:
        return self.raw.get("prompt", "")


# =============================================================================
# Response Builders
# =============================================================================

class Response:
    """Response builders for hook output."""

    @staticmethod
    def allow(reason: str = "") -> dict:
        """Allow the tool to proceed (PreToolUse)."""
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "permissionDecisionReason": reason or "Allowed by hook"
            }
        }

    @staticmethod
    def deny(reason: str) -> dict:
        """Block the tool from proceeding (PreToolUse)."""
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason
            }
        }

    @staticmethod
    def message(text: str, event: EventType = "PostToolUse") -> dict:
        """Return a message to Claude (any hook)."""
        return {
            "hookSpecificOutput": {
                "hookEventName": event,
                "message": text
            }
        }

    @staticmethod
    def continue_with(text: str) -> dict:
        """Continue with a message (PreCompact, Stop)."""
        return {
            "result": "continue",
            "message": text
        }

    @staticmethod
    def modify_input(new_input: dict) -> dict:
        """Modify the tool input before execution (PreToolUse)."""
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "modifiedInput": new_input
            }
        }


# =============================================================================
# Pattern Matching Utilities
# =============================================================================

class Patterns:
    """Common pattern matching utilities."""

    @staticmethod
    def matches_glob(path: str, patterns: list[str]) -> str | None:
        """
        Check if path matches any glob pattern.
        Returns matching pattern or None.
        """
        path = os.path.normpath(path)
        filename = os.path.basename(path)

        for pattern in patterns:
            if fnmatch.fnmatch(path, pattern):
                return pattern
            if fnmatch.fnmatch(filename, pattern):
                return pattern
            # Substring match for simple patterns
            if not any(c in pattern for c in '*?['):
                if pattern in path:
                    return pattern
        return None

    @staticmethod
    def matches_command(command: str, patterns: list[str]) -> str | None:
        r"""
        Check if command matches any pattern.
        Patterns can be:
        - Simple prefix: "git push"
        - Regex: r"rm\s+-rf"
        """
        command = command.strip()
        for pattern in patterns:
            if pattern.startswith("r\"") or pattern.startswith("r'"):
                # Regex pattern
                regex = pattern[2:-1]
                if re.search(regex, command):
                    return pattern
            elif command.startswith(pattern) or pattern in command:
                return pattern
        return None

    @staticmethod
    def extract_command_name(command: str) -> str:
        """Extract the base command name from a command string."""
        parts = command.strip().split()
        if not parts:
            return ""
        # Skip env vars and sudo
        for part in parts:
            if '=' not in part and part != 'sudo':
                return part
        return parts[-1] if parts else ""


# =============================================================================
# Rate Limiting (Thread-Safe)
# =============================================================================

class RateLimiter:
    """Thread-safe rate limiter for hook actions."""

    # Class-level lock for all rate limiters
    _lock = threading.Lock()

    def __init__(self, name: str, max_count: int, window_secs: int):
        """
        Args:
            name: Unique identifier for this limiter
            max_count: Maximum actions in window
            window_secs: Window size in seconds
        """
        self.name = name
        self.max_count = max_count
        self.window_secs = window_secs
        self.state_key = f"rate-limit-{name}"

    def check(self) -> bool:
        """Check if action is allowed (doesn't consume)."""
        with self._lock:
            state = read_state(self.state_key, {"timestamps": []})
            now = time.time()
            cutoff = now - self.window_secs
            timestamps = [t for t in state.get("timestamps", []) if t > cutoff]
            return len(timestamps) < self.max_count

    def consume(self) -> bool:
        """Try to consume one action. Returns True if allowed."""
        with self._lock:
            state = read_state(self.state_key, {"timestamps": []})
            now = time.time()
            cutoff = now - self.window_secs
            timestamps = [t for t in state.get("timestamps", []) if t > cutoff]

            if len(timestamps) >= self.max_count:
                return False

            timestamps.append(now)
            write_state(self.state_key, {"timestamps": timestamps})
            return True

    def reset(self):
        """Reset the rate limiter."""
        with self._lock:
            write_state(self.state_key, {"timestamps": []})

    def remaining(self) -> int:
        """Get remaining actions in current window."""
        with self._lock:
            state = read_state(self.state_key, {"timestamps": []})
            now = time.time()
            cutoff = now - self.window_secs
            timestamps = [t for t in state.get("timestamps", []) if t > cutoff]
            return max(0, self.max_count - len(timestamps))


# =============================================================================
# Handler Decorators
# =============================================================================

def hook_handler(
    name: str,
    event: EventType = "PreToolUse",
    tools: list[str] | None = None,
):
    """
    Decorator for hook handler functions.

    Args:
        name: Hook name for logging
        event: Event type this handler processes
        tools: List of tools to handle (None = all)

    Usage:
        @hook_handler("my_hook", event="PreToolUse", tools=["Bash", "Write"])
        def handle(ctx: PreToolUseContext) -> Response | None:
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        @graceful_main(name)
        def wrapper():
            try:
                raw = json.load(sys.stdin)
            except (json.JSONDecodeError, Exception):
                sys.exit(0)

            # Filter by tool if specified
            tool_name = raw.get("tool_name", "")
            if tools and tool_name not in tools:
                sys.exit(0)

            # Create appropriate context
            if event == "PreToolUse":
                ctx = PreToolUseContext(raw)
            elif event == "PostToolUse":
                ctx = PostToolUseContext(raw)
            elif event in ("SessionStart", "SessionEnd"):
                ctx = SessionContext(raw)
            elif event == "UserPromptSubmit":
                ctx = PromptContext(raw)
            elif event in ("SubagentStart", "SubagentStop"):
                ctx = SubagentContext(raw)
            else:
                ctx = BaseContext(raw)

            result = func(ctx)

            if result:
                print(json.dumps(result))

            sys.exit(0)

        return wrapper
    return decorator


def dispatch_handler(name: str, event: EventType = "PreToolUse"):
    """
    Decorator for handlers called from dispatchers.
    Returns the handler function directly (no stdin/stdout handling).

    Usage:
        @dispatch_handler("file_protection")
        def check_protection(ctx: PreToolUseContext) -> dict | None:
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(raw: dict) -> dict | None:
            try:
                # Create appropriate context
                if event == "PreToolUse":
                    ctx = PreToolUseContext(raw)
                elif event == "PostToolUse":
                    ctx = PostToolUseContext(raw)
                else:
                    ctx = BaseContext(raw)

                return func(ctx)
            except Exception as e:
                log_event(name, "error", {"error": str(e)}, "error")
                return None

        return wrapper
    return decorator


# =============================================================================
# Convenience Functions
# =============================================================================

def expand_path(path: str) -> str:
    """Expand ~ and normalize path."""
    if path.startswith("~"):
        path = os.path.expanduser(path)
    return os.path.normpath(path)


def relative_to_cwd(path: str, cwd: str = None) -> str:
    """Make path relative to cwd if possible."""
    cwd = cwd or os.getcwd()
    try:
        return os.path.relpath(path, cwd)
    except ValueError:
        return path


# =============================================================================
# Entry Point Helper
# =============================================================================

def run_standalone(handler: Callable[[dict], dict | None]):
    """
    Run a handler function as a standalone script.
    Reads from stdin, calls handler, writes to stdout.

    Usage:
        if __name__ == "__main__":
            run_standalone(my_handler)
    """
    try:
        raw = json.load(sys.stdin)
    except (json.JSONDecodeError, Exception):
        sys.exit(0)

    result = handler(raw)
    if result:
        print(json.dumps(result))

    sys.exit(0)

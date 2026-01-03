#!/home/jonglaser/.claude/data/venv/bin/python3
"""
Claude Code Hook SDK - Typed abstractions for hook development.

Provides:
- Typed context dataclasses (PreToolUseContext, PostToolUseContext, etc.)
- Response builders (allow, deny, message, continue_with_message)
- Common patterns (file matching, command parsing, rate limiting)
- Handler decorators for cleaner hook code

Usage:
    from hooks.hook_sdk import (
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
import json
import os
import re
import sys
import threading
import time
from pathlib import Path
from dataclasses import dataclass, field
from functools import lru_cache, wraps
from typing import Any, Callable, Literal

# Import base utilities
from hooks.hook_utils import (
    graceful_main,
    log_event,
    read_state,
    write_state,
    get_session_id,
    # Event detection - canonical implementations in hook_utils
    detect_event,
    is_post_tool_use,
    is_pre_tool_use,
    get_tool_response,
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


# =============================================================================
# Context Dataclasses
# =============================================================================

@dataclass
class ToolInput:
    """Parsed tool input with typed accessors.

    Supports attribute access via __getattr__ for dynamic fields.
    Explicit properties below provide IDE autocomplete and type hints.
    """
    raw: dict = field(default_factory=dict)

    # Explicit properties for IDE autocomplete and type hints
    @property
    def file_path(self) -> str:
        return self.raw.get("file_path", "")

    @property
    def command(self) -> str:
        return self.raw.get("command", "")

    @property
    def content(self) -> str:
        return self.raw.get("content", "")

    @property
    def pattern(self) -> str:
        return self.raw.get("pattern", "")

    @property
    def prompt(self) -> str:
        return self.raw.get("prompt", "")

    def __getattr__(self, name: str) -> Any:
        """Fallback for any attribute not explicitly defined."""
        if name.startswith('_'):
            raise AttributeError(name)
        return self.raw.get(name)

    def get(self, key: str, default: Any = None) -> Any:
        return self.raw.get(key, default)


@dataclass
class ToolResult:
    """Parsed tool result with typed accessors.

    Provides convenience properties for exit code, stdout/stderr, and success status.
    """
    raw: dict = field(default_factory=dict)

    @property
    def exit_code(self) -> int | None:
        """Exit code (handles both exit_code and exitCode keys)."""
        code = self.raw.get("exit_code")
        if code is None:
            code = self.raw.get("exitCode")
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
    def content(self) -> str:
        """Extract content from result (handles dict, string, and various key names).

        Tries: content, output, text keys for dicts; returns string directly otherwise.
        """
        if isinstance(self.raw, str):
            return self.raw
        if isinstance(self.raw, dict):
            return (
                self.raw.get("content", "")
                or self.raw.get("output", "")
                or self.raw.get("text", "")
                or ""
            )
        return str(self.raw) if self.raw else ""

    @property
    def success(self) -> bool:
        return self.exit_code == 0 if self.exit_code is not None else True

    def __getattr__(self, name: str) -> Any:
        """Fallback for any attribute not explicitly defined."""
        if name.startswith('_'):
            raise AttributeError(name)
        return self.raw.get(name)

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
        return self.raw.get("cwd", str(Path.cwd()))

    @property
    def transcript_path(self) -> str:
        return self.raw.get("transcript_path", "")

    def __getattr__(self, name: str) -> Any:
        """Fallback for any attribute not explicitly defined."""
        if name.startswith('_'):
            raise AttributeError(name)
        return self.raw.get(name)

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


# =============================================================================
# HookState - Simplified State Management for Handlers
# =============================================================================

class HookState:
    """Unified state management for handlers.

    Provides a clean API for common state management patterns with TTL,
    pruning, and timestamping. Consolidates StateManager functionality.

    Usage:
        # Session-scoped state with TTL
        state = HookState("file_monitor", use_session=True)
        data = state.load(session_id, default={"reads": {}})
        state.save_with_pruning(data, session_id, max_entries=100, items_key="reads")

        # Global state
        state = HookState("warnings", use_session=False)
        warnings = state.load(default={"items": []})
    """

    def __init__(self, namespace: str, use_session: bool = True, max_age_secs: int = None):
        """Initialize hook state.

        Args:
            namespace: State namespace/key (e.g., "file_monitor", "tdd-warnings")
            use_session: Use session-based storage (True) or global (False)
            max_age_secs: Max age in seconds before state expires (None = no expiry)
        """
        self.namespace = namespace
        self.use_session = use_session
        self.max_age_secs = max_age_secs

    def load(self, session_id: str = None, default: dict = None, max_age_secs: int = None) -> dict:
        """Load state, returning default if missing or expired.

        Args:
            session_id: Session ID (required if use_session=True)
            default: Default value if state doesn't exist or is expired
            max_age_secs: Override instance max_age_secs for this load

        Returns:
            State dict (loaded or default copy)
        """
        if default is None:
            default = {}

        if self.use_session:
            from hooks.hook_utils.session import read_session_state
            state = read_session_state(self.namespace, session_id, default)
        else:
            state = read_state(self.namespace, default)

        # Check TTL expiry
        max_age = max_age_secs if max_age_secs is not None else self.max_age_secs
        if max_age is not None:
            last_update = state.get("_updated", 0)
            if time.time() - last_update > max_age:
                return default.copy()

        return state

    def save(self, data: dict, session_id: str = None) -> bool:
        """Save state with automatic timestamp.

        Args:
            data: State dict to save
            session_id: Session ID (required if use_session=True)

        Returns:
            True on success
        """
        data["_updated"] = time.time()

        if self.use_session:
            from hooks.hook_utils.session import write_session_state
            return write_session_state(self.namespace, data, session_id)
        else:
            return write_state(self.namespace, data)

    def save_with_pruning(
        self,
        data: dict,
        session_id: str = None,
        max_entries: int = None,
        items_key: str = None,
        time_key: str = "_time"
    ) -> bool:
        """Save state with optional pruning of old entries.

        Common pattern: Save state and limit size by keeping newest entries.

        Args:
            data: State dict to save
            session_id: Session ID (required if use_session=True)
            max_entries: Max number of entries to keep in items dict (no limit if None)
            items_key: Key in state containing items to prune (e.g., "reads", "searches")
                      If None, no pruning is performed
            time_key: Key in each item containing timestamp (used for pruning order)

        Returns:
            True on success
        """
        # Prune items if needed
        if max_entries and items_key and items_key in data:
            items = data.get(items_key, {})
            if len(items) > max_entries:
                sorted_items = sorted(
                    items.items(),
                    key=lambda x: x[1].get(time_key, 0),
                    reverse=True
                )
                data[items_key] = dict(sorted_items[:max_entries])

        # Add timestamp
        data["_updated"] = time.time()

        # Save
        if self.use_session:
            from hooks.hook_utils.session import write_session_state
            return write_session_state(self.namespace, data, session_id)
        else:
            return write_state(self.namespace, data)

    def update(self, updater, session_id: str = None, default: dict = None) -> bool:
        """Read-modify-write pattern.

        Args:
            updater: Function that takes current state and returns updated state
            session_id: Session ID (required if use_session=True)
            default: Default state if missing

        Returns:
            True on success
        """
        data = self.load(session_id, default)
        updated = updater(data)
        return self.save(updated, session_id)


# =============================================================================
# BlockingHook - Base Class for PreToolUse Denials
# =============================================================================

class BlockingHook:
    """Base for PreToolUse hooks that can deny operations.

    Subclasses implement check() which returns deny response or None to allow.

    Example:
        class FileBlocker(BlockingHook):
            def check(self, ctx: PreToolUseContext) -> dict | None:
                if ctx.tool_input.file_path.endswith('.secret'):
                    return self.deny("Cannot access secret files")
                return None

        # Usage in dispatcher
        blocker = FileBlocker("file_blocker")
        result = blocker(ctx)  # Returns deny response or None
    """

    def __init__(self, name: str):
        """Initialize blocking hook.

        Args:
            name: Hook identifier for logging
        """
        self.name = name

    def check(self, ctx) -> dict | None:
        """Check if operation should be blocked.

        Override this method in subclasses.

        Args:
            ctx: Context object (typically PreToolUseContext)

        Returns:
            Deny response dict if blocked, None to allow
        """
        raise NotImplementedError("Subclasses must implement check()")

    def deny(self, reason: str) -> dict:
        """Build deny response.

        Args:
            reason: Human-readable reason for denial

        Returns:
            Hook response dict
        """
        return Response.deny(reason)

    def __call__(self, ctx) -> dict | None:
        """Call the hook (allows use as callable)."""
        return self.check(ctx)


# =============================================================================
# HookHandler - Base Class for All Handlers (P5.11)
# =============================================================================

class HookHandler:
    """Base class for hook handlers with applies/handle pattern.

    Provides a clean interface for dispatcher routing. Subclasses implement:
    - applies(ctx) -> bool: Whether this handler should run
    - handle(ctx) -> dict | None: Process and return response

    Example:
        class MyHandler(HookHandler):
            name = "my_handler"
            tools = ["Bash", "Read"]  # Only run for these tools

            def handle(self, ctx: PreToolUseContext) -> dict | None:
                if "dangerous" in ctx.tool_input.command:
                    return self.deny("Dangerous command blocked")
                return None

        # Usage in dispatcher
        handler = MyHandler()
        if handler.applies(ctx):
            result = handler.handle(ctx)
    """

    # Class attributes (override in subclasses)
    name: str = "base_handler"
    tools: list[str] | None = None  # Filter by tool name (None = all tools)
    event: EventType = "PreToolUse"  # Event type this handler processes

    def applies(self, ctx) -> bool:
        """Check if this handler should run for the given context.

        Override for custom filtering logic. Default checks tool name.

        Args:
            ctx: Context object (PreToolUseContext, PostToolUseContext, etc.)

        Returns:
            True if handler should run, False to skip
        """
        if self.tools is not None:
            tool_name = getattr(ctx, 'tool_name', None)
            if tool_name and tool_name not in self.tools:
                return False
        return True

    def handle(self, ctx) -> dict | None:
        """Process the context and return a response.

        Override this method in subclasses.

        Args:
            ctx: Context object

        Returns:
            Response dict or None to continue without message
        """
        raise NotImplementedError("Subclasses must implement handle()")

    def _create_context(self, raw: dict):
        """Create appropriate context object from raw dict."""
        if self.event == "PreToolUse":
            return PreToolUseContext(raw)
        elif self.event == "PostToolUse":
            return PostToolUseContext(raw)
        else:
            return BaseContext(raw)

    def __call__(self, raw: dict) -> dict | None:
        """Entry point - creates context, checks applies, calls handle.

        Args:
            raw: Raw hook input dict

        Returns:
            Response dict or None
        """
        try:
            ctx = self._create_context(raw)
            if not self.applies(ctx):
                return None
            return self.handle(ctx)
        except Exception as e:
            log_event(self.name, "error", {"error": str(e)}, "error")
            return None

    # Convenience methods for building responses
    def allow(self, reason: str = "") -> dict:
        """Allow with optional message (PreToolUse)."""
        return Response.allow(reason)

    def deny(self, reason: str) -> dict:
        """Deny the operation (PreToolUse)."""
        return Response.deny(reason)

    def message(self, text: str) -> dict:
        """Return a message to Claude."""
        return Response.message(text, self.event)


# =============================================================================
# StatefulHandler - Base Class for Stateful Handlers (P5.12)
# =============================================================================

class StatefulHandler(HookHandler):
    """Base class for handlers that maintain session state.

    Provides automatic state loading/saving with TTL expiration and pruning.
    Subclasses implement process() instead of handle().

    Example:
        class FileTracker(StatefulHandler):
            name = "file_tracker"
            namespace = "file_tracker"
            tools = ["Read", "Edit"]
            event = "PreToolUse"
            default_state = {"files": {}, "count": 0}
            max_entries = 100
            items_key = "files"

            def process(self, ctx, state: dict) -> dict | None:
                file_path = ctx.tool_input.file_path
                state["files"][file_path] = {"time": time.time()}
                state["count"] += 1
                if state["count"] > 50:
                    return self.message(f"Accessed {state['count']} files")
                return None

        # Usage
        handler = FileTracker()
        result = handler(raw)  # Automatically loads/saves state
    """

    # Class attributes (override in subclasses)
    namespace: str = "stateful_handler"  # State namespace for storage
    default_state: dict = None  # Default state structure
    max_age_secs: int = 86400  # State expires after 24 hours
    max_entries: int | None = None  # Max items to keep (None = no limit)
    items_key: str | None = None  # Key containing items to prune
    time_key: str = "_time"  # Timestamp key in items (for pruning order)

    def __init__(self):
        """Initialize stateful handler with HookState instance."""
        self._hook_state = HookState(
            self.namespace,
            use_session=True,
            max_age_secs=self.max_age_secs
        )

    def _get_default_state(self) -> dict:
        """Get default state, ensuring fresh copy."""
        if self.default_state is None:
            return {}
        return self.default_state.copy()

    def load_state(self, session_id: str) -> dict:
        """Load state for session.

        Args:
            session_id: Session identifier

        Returns:
            State dict (loaded or default copy)
        """
        return self._hook_state.load(
            session_id=session_id,
            default=self._get_default_state()
        )

    def save_state(self, session_id: str, state: dict) -> bool:
        """Save state with optional pruning.

        Args:
            session_id: Session identifier
            state: State dict to save

        Returns:
            True on success
        """
        if self.max_entries and self.items_key:
            return self._hook_state.save_with_pruning(
                state,
                session_id=session_id,
                max_entries=self.max_entries,
                items_key=self.items_key,
                time_key=self.time_key
            )
        return self._hook_state.save(state, session_id)

    def handle(self, ctx) -> dict | None:
        """Handle with automatic state loading/saving.

        Loads state, calls process(), saves state.
        Override process() instead of this method.
        """
        session_id = ctx.session_id
        state = self.load_state(session_id)
        result = self.process(ctx, state)
        self.save_state(session_id, state)
        return result

    def process(self, ctx, state: dict) -> dict | None:
        """Process the context with access to state.

        Override this method in subclasses. Modify state dict in place.

        Args:
            ctx: Context object
            state: Mutable state dict

        Returns:
            Response dict or None
        """
        raise NotImplementedError("Subclasses must implement process()")


# =============================================================================
# Pattern Matching Utilities
# =============================================================================

class Patterns:
    """Centralized pattern matching utilities for all hooks.

    Provides unified methods for:
    - Glob pattern matching (fnmatch-based, with caching)
    - Command pattern matching (prefix and regex)
    - Pre-compiled regex pattern matching
    - Path pattern matching (with brace expansion support)
    """

    @staticmethod
    def matches_glob(path: str, patterns: list[str]) -> str | None:
        """
        Check if path matches any glob pattern.
        Returns matching pattern or None.
        """
        # os.path.normpath needed to collapse .. sequences (Path doesn't do this)
        path = os.path.normpath(path)
        filename = Path(path).name

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
    def matches_compiled(value: str, compiled_patterns: list) -> bool:
        """
        Check if value matches any pre-compiled regex pattern.

        Args:
            value: String to match
            compiled_patterns: List of compiled regex patterns (re.Pattern objects)

        Returns:
            True if value matches any pattern, False otherwise

        Example:
            patterns = SmartPermissions.get_read()  # Pre-compiled patterns
            if Patterns.matches_compiled(file_path, patterns):
                approve()
        """
        value_lower = value.lower()
        return any(p.search(value_lower) for p in compiled_patterns)

    @staticmethod
    def find_matching_pattern(value: str, compiled_patterns: list) -> str | None:
        """
        Find the first matching compiled regex pattern.

        Args:
            value: String to match
            compiled_patterns: List of compiled regex patterns (re.Pattern objects)

        Returns:
            Pattern string that matched, or None if no match

        Example:
            patterns = get_protected_patterns_compiled()
            matched = Patterns.find_matching_pattern(file_path, patterns)
            if matched:
                deny(f"Blocked: matches {matched}")
        """
        for p in compiled_patterns:
            if p.search(value):
                return p.pattern
        return None

    @staticmethod
    @lru_cache(maxsize=256)
    def compile_pattern(pattern: str) -> re.Pattern:
        """
        Compile glob pattern to regex with caching.

        Converts patterns like "**/*.ts" to compiled regex patterns.
        Supports:
        - ** : matches multiple directory levels
        - * : matches within single directory
        - {a,b} : brace expansion

        Args:
            pattern: Glob pattern string

        Returns:
            Compiled regex pattern

        Example:
            pat = Patterns.compile_pattern("src/**/*.ts")
            if pat.match("src/api/users.ts"):
                apply_rule()
        """
        regex = pattern.replace(".", r"\.")
        regex = regex.replace("**", "<<<DOUBLE>>>")
        regex = regex.replace("*", "[^/]*")
        regex = regex.replace("<<<DOUBLE>>>", ".*")
        regex = "^" + regex + "$"
        return re.compile(regex)

    @staticmethod
    def matches_path_pattern(path: str, pattern: str) -> bool:
        """
        Check if file path matches a glob-like pattern with brace expansion.

        Supports:
        - **/*.ts - matches any .ts file in any subdirectory
        - src/**/* - matches anything under src/
        - {src,lib}/**/*.ts - matches .ts in src/ or lib/

        Args:
            path: File path to check
            pattern: Glob pattern

        Returns:
            True if path matches pattern, False otherwise
        """
        # Handle brace expansion {a,b}
        if "{" in pattern and "}" in pattern:
            match = re.match(r"(.*)\{([^}]+)\}(.*)", pattern)
            if match:
                prefix, options, suffix = match.groups()
                for option in options.split(","):
                    expanded = prefix + option.strip() + suffix
                    if Patterns.matches_path_pattern(path, expanded):
                        return True
                return False

        # Use cached compiled pattern
        compiled = Patterns.compile_pattern(pattern)
        return bool(compiled.match(path))


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


# =============================================================================
# Handler Decorators
# =============================================================================

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


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Context classes
    "ToolInput",
    "ToolResult",
    "BaseContext",
    "PreToolUseContext",
    "PostToolUseContext",
    # Response builders
    "Response",
    # State management
    "HookState",
    # Base classes
    "BlockingHook",
    "HookHandler",
    "StatefulHandler",
    # Pattern matching
    "Patterns",
    # Rate limiting
    "RateLimiter",
    # Decorators and helpers
    "dispatch_handler",
    "run_standalone",
    # Event types
    "EventType",
    # Re-exports from hook_utils (commonly used)
    "log_event",
    "read_state",
    "write_state",
    "get_session_id",
    "graceful_main",
    "detect_event",
    "is_post_tool_use",
    "is_pre_tool_use",
    "get_tool_response",
]

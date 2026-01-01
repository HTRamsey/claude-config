#!/home/jonglaser/.claude/data/venv/bin/python3
"""
Base class for hook dispatchers.

Provides common functionality for PreToolUse and PostToolUse dispatchers:
- Lazy handler loading with caching
- Timeout-protected handler execution
- Profiling support (HOOK_PROFILE=1)
- Handler validation
- Logging integration
- Batch session state loading (optimization)
- Fast JSON parsing via msgspec

Subclasses override:
- DISPATCHER_NAME: Name for logging
- HOOK_EVENT_NAME: "PreToolUse" or "PostToolUse"
- ALL_HANDLERS: List of handler names
- TOOL_HANDLERS: Tool-to-handler mapping
- _import_handler(): Import logic for each handler
- _execute_handler(): Handler execution logic with special cases
- _build_result(): Build the final result from messages
"""
import atexit
import json
import os
import sys
import time
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from pathlib import Path
from typing import Any, Callable

# Profiling mode (set HOOK_PROFILE=1 to enable)
_PROFILE_MODE = os.environ.get("HOOK_PROFILE", "0") == "1"

# Handler timeout in seconds (default 1s, configurable via HANDLER_TIMEOUT env var in ms)
_HANDLER_TIMEOUT = float(os.environ.get("HANDLER_TIMEOUT", "1000")) / 1000.0

# Thread pool for timeout-protected handler execution (shared across dispatchers)
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="hook")

# Register cleanup on exit to prevent resource leaks
atexit.register(_executor.shutdown, wait=False)

# Import shared utilities
try:
    from hook_utils import graceful_main, log_event, is_hook_disabled, flush_pending_writes
    HAS_UTILS = True
except ImportError:
    HAS_UTILS = False
    def graceful_main(name):
        def decorator(func):
            return func
        return decorator
    def log_event(*args, **kwargs):
        pass
    def is_hook_disabled(name):
        return False
    def flush_pending_writes():
        return 0

# Fast JSON parsing via msgspec (10x faster)
try:
    from config import fast_json_loads, HAS_MSGSPEC
except ImportError:
    HAS_MSGSPEC = False
    def fast_json_loads(data):
        return json.loads(data if isinstance(data, str) else data.decode())


class BaseDispatcher(ABC):
    """Abstract base class for hook dispatchers."""

    # Subclasses must override these
    DISPATCHER_NAME: str = "base_dispatcher"
    HOOK_EVENT_NAME: str = "Unknown"
    ALL_HANDLERS: list[str] = []
    TOOL_HANDLERS: dict[str, list[str]] = {}

    def __init__(self):
        self._handlers: dict[str, Any] = {}
        self._validated = False
        self._profile_timings: dict[str, list[float]] = {}

    @abstractmethod
    def _import_handler(self, name: str) -> Any:
        """Import and return the handler for the given name.

        Returns the handler callable (or tuple of callables), or None if not found.
        """
        pass

    def _execute_handler(self, name: str, handler: Any, ctx: dict) -> dict | None:
        """Execute handler logic. Override for special cases.

        Default implementation just calls handler(ctx).
        """
        return handler(ctx)

    def _route_dual_handler(
        self,
        handler: tuple,
        ctx: dict,
        tool_mapping: dict[str, int]
    ) -> dict | None:
        """Route to one of two handlers based on tool_name.

        Args:
            handler: Tuple of (handler0, handler1)
            ctx: Hook context
            tool_mapping: Maps tool_name to handler index (0 or 1)

        Returns:
            Handler result or None if tool not in mapping
        """
        tool_name = ctx.get("tool_name", "")
        handler_idx = tool_mapping.get(tool_name)
        if handler_idx is not None:
            return handler[handler_idx](ctx)
        return None

    def _build_result(self, messages: list[str]) -> dict | None:
        """Build the final result from collected messages.

        Override in subclasses for different result formats.
        """
        if messages:
            return {
                "hookSpecificOutput": {
                    "hookEventName": self.HOOK_EVENT_NAME,
                    "message": " | ".join(messages[:3])
                }
            }
        return None

    def get_handler(self, name: str) -> Any:
        """Lazy-load and cache handler module."""
        if name not in self._handlers:
            try:
                self._handlers[name] = self._import_handler(name)
            except ImportError as e:
                log_event(self.DISPATCHER_NAME, "import_error", {"handler": name, "error": str(e)})
                self._handlers[name] = None
        return self._handlers.get(name)

    def validate_handlers(self) -> None:
        """Validate all handlers can be imported. Called once at startup."""
        failed = []
        for name in self.ALL_HANDLERS:
            handler = self.get_handler(name)
            if handler is None and name in self._handlers:
                failed.append(name)
            elif handler is not None and not callable(handler):
                if isinstance(handler, tuple):
                    if not all(callable(h) for h in handler):
                        failed.append(f"{name} (not all callable)")
                else:
                    failed.append(f"{name} (not callable)")

        if failed:
            log_event(self.DISPATCHER_NAME, "startup_validation", {
                "failed_handlers": failed,
                "count": len(failed)
            })
            print(f"[{self.DISPATCHER_NAME}] Warning: {len(failed)} handlers failed: {', '.join(failed)}",
                  file=sys.stderr)

    def run_handler(self, name: str, ctx: dict) -> dict | None:
        """Run a single handler with timeout protection."""
        if is_hook_disabled(name):
            log_event(self.DISPATCHER_NAME, "handler_skipped", {"handler": name, "reason": "disabled"})
            return None

        handler = self.get_handler(name)
        if handler is None:
            return None

        start_time = time.perf_counter()
        result = None
        error = None

        try:
            future = _executor.submit(self._execute_handler, name, handler, ctx)
            result = future.result(timeout=_HANDLER_TIMEOUT)
        except FuturesTimeoutError:
            error = f"timeout after {_HANDLER_TIMEOUT:.1f}s"
            log_event(self.DISPATCHER_NAME, "handler_timeout", {"handler": name, "timeout_s": _HANDLER_TIMEOUT})
        except Exception as e:
            error = str(e)
            log_event(self.DISPATCHER_NAME, "handler_error", {"handler": name, "error": error})

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        if _PROFILE_MODE:
            self._profile_timings.setdefault(name, []).append(elapsed_ms)
            print(f"[{self.DISPATCHER_NAME}] {name}: {elapsed_ms:.1f}ms", file=sys.stderr)

        log_event(self.DISPATCHER_NAME, "handler_timing", {
            "handler": name,
            "elapsed_ms": round(elapsed_ms, 2),
            "tool": ctx.get("tool_name", ""),
            "success": error is None
        })

        return result

    def dispatch(self, ctx: dict) -> dict | None:
        """Dispatch to appropriate handlers based on tool name."""
        dispatch_start = time.perf_counter()
        tool_name = ctx.get("tool_name", "")

        handlers = self.TOOL_HANDLERS.get(tool_name, [])
        if not handlers:
            return None

        messages = []

        for handler_name in handlers:
            result = self.run_handler(handler_name, ctx)

            if result and isinstance(result, dict):
                hook_output = result.get("hookSpecificOutput", {})

                # Check for early termination (subclasses can override)
                if self._should_terminate(result, handler_name, tool_name):
                    return result

                # Collect message
                message = self._extract_message(hook_output)
                if message:
                    messages.append(message)

        # Flush any batched state writes
        write_count = flush_pending_writes()

        if _PROFILE_MODE:
            total_ms = (time.perf_counter() - dispatch_start) * 1000
            print(f"[{self.DISPATCHER_NAME}] TOTAL for {tool_name}: {total_ms:.1f}ms ({len(handlers)} handlers, {write_count} writes)",
                  file=sys.stderr)

        return self._build_result(messages)

    def _should_terminate(self, result: dict, handler_name: str, tool_name: str) -> bool:
        """Check if dispatch should terminate early. Override for deny behavior."""
        return False

    def _extract_message(self, hook_output: dict) -> str:
        """Extract message from hook output. Override for different formats."""
        return hook_output.get("message", "")

    def run(self) -> None:
        """Main entry point - read stdin, dispatch, output result."""
        if not self._validated:
            self.validate_handlers()
            self._validated = True

        try:
            # Use fast JSON parsing when available
            stdin_data = sys.stdin.read()
            if HAS_MSGSPEC and stdin_data:
                ctx = fast_json_loads(stdin_data)
            else:
                ctx = json.loads(stdin_data) if stdin_data else {}
        except (json.JSONDecodeError, Exception):
            sys.exit(0)

        result = self.dispatch(ctx)
        if result:
            print(json.dumps(result))

        sys.exit(0)

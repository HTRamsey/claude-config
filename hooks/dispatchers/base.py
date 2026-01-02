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
- ResultStrategy: Strategy pattern for result building
"""
import atexit
import importlib
import json
import os
import signal
import sys
import time
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from dataclasses import dataclass
from typing import Any, Callable

# Profiling mode (set HOOK_PROFILE=1 to enable)
_PROFILE_MODE = os.environ.get("HOOK_PROFILE", "0") == "1"

# Handler timeout in seconds (default 1s, configurable via HANDLER_TIMEOUT env var in ms)
# Wrapped in try/except to handle invalid env var values gracefully
try:
    _HANDLER_TIMEOUT = float(os.environ.get("HANDLER_TIMEOUT", "1000")) / 1000.0
except (ValueError, TypeError):
    _HANDLER_TIMEOUT = 1.0  # Default to 1 second on invalid input

# Fast handlers that bypass thread pool (sub-10ms execution, simple logic)
_FAST_HANDLERS = frozenset({
    "file_protection",
    "dangerous_command_blocker",
})

# Thread pool for timeout-protected handler execution (shared across dispatchers)
# 4 workers allows I/O-bound handlers to run concurrently without blocking
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="hook")


def _shutdown_handler(signum: int, frame) -> None:
    """Handle SIGTERM/SIGINT for clean shutdown.

    atexit handlers don't run on signals, so we need explicit signal handling.
    """
    _executor.shutdown(wait=False, cancel_futures=True)
    sys.exit(128 + signum)


# Register signal handlers for clean shutdown
signal.signal(signal.SIGTERM, _shutdown_handler)
signal.signal(signal.SIGINT, _shutdown_handler)

# Register cleanup on exit to prevent resource leaks (for normal exit)
atexit.register(_executor.shutdown, wait=False)

# Import shared utilities
from hooks.hook_utils import graceful_main, log_event, is_hook_disabled, flush_pending_writes
from hooks.config import fast_json_loads
from hooks.hook_sdk import Response


@dataclass
class RoutingRule:
    """Route tool calls to specific handler indices for dual handlers."""
    tool_patterns: dict[str, int]  # tool_name → handler index (0 or 1)
    default: int = 0


class HandlerRegistry:
    """Manages handlers and their routing rules.

    Supports single handlers and dual handlers (tuples) with intelligent routing.
    """

    def __init__(self):
        self.handlers: dict[str, Any] = {}
        self.routing_rules: dict[str, RoutingRule] = {}
        self.custom_executors: dict[str, Callable] = {}

    def register(self, name: str, handler: Any, routing: RoutingRule = None, executor: Callable = None):
        """Register a handler with optional routing rule and custom executor.

        Args:
            name: Handler name
            handler: Handler callable or tuple of callables
            routing: RoutingRule for dual handlers
            executor: Custom executor function for special-case handling
        """
        self.handlers[name] = handler
        if routing:
            self.routing_rules[name] = routing
        if executor:
            self.custom_executors[name] = executor

    def get_handler_for_tool(self, name: str, tool_name: str) -> Callable | None:
        """Get the appropriate handler function for a tool call.

        For dual handlers, routes to the correct index based on tool_name.
        For single handlers, returns directly.

        Args:
            name: Handler name
            tool_name: Tool name from context

        Returns:
            Handler callable or None if not found
        """
        handler = self.handlers.get(name)
        if handler is None:
            return None

        # Single handler
        if not isinstance(handler, tuple):
            return handler

        # Dual handler - route based on tool_name
        rule = self.routing_rules.get(name)
        if rule:
            idx = rule.tool_patterns.get(tool_name, rule.default)
            if idx < len(handler):
                return handler[idx]

        # Default to first handler if no routing rule
        return handler[0] if handler else None

    def has_custom_executor(self, name: str) -> bool:
        """Check if handler has a custom executor."""
        return name in self.custom_executors

    def get_custom_executor(self, name: str) -> Callable | None:
        """Get custom executor for handler if it exists."""
        return self.custom_executors.get(name)




class ResultStrategy(ABC):
    """Strategy for building hook results.

    Encapsulates termination logic, message extraction, and result building
    for different hook types (PreToolUse vs PostToolUse).
    """

    @abstractmethod
    def should_terminate(self, result: dict, handler_name: str) -> bool:
        """Decide if dispatch should stop after this handler.

        Args:
            result: Handler result dict
            handler_name: Name of handler that produced result

        Returns:
            True if dispatch should terminate, False to continue
        """
        pass

    @abstractmethod
    def extract_message(self, hook_output: dict) -> str | None:
        """Extract message from handler output.

        Args:
            hook_output: The hookSpecificOutput dict from handler result

        Returns:
            Message string or None if no message to extract
        """
        pass

    @abstractmethod
    def build_result(self, messages: list[str]) -> dict | None:
        """Build final result from collected messages.

        Args:
            messages: List of collected messages from handlers

        Returns:
            Final result dict or None if no result to return
        """
        pass


class PreToolStrategy(ResultStrategy):
    """Strategy for PreToolUse - can deny and terminate dispatch."""

    def should_terminate(self, result: dict, handler_name: str) -> bool:
        """PreToolUse terminates on deny decisions.

        Args:
            result: Handler result dict
            handler_name: Name of handler that produced result

        Returns:
            True if permissionDecision is "deny", False otherwise
        """
        hook_output = result.get("hookSpecificOutput", {})
        is_deny = hook_output.get("permissionDecision") == "deny"
        if is_deny:
            log_event("pre_tool_dispatcher", "denied", {
                "handler": handler_name
            })
        return is_deny

    def extract_message(self, hook_output: dict) -> str | None:
        """Extract permissionDecisionReason from hook output.

        Args:
            hook_output: The hookSpecificOutput dict

        Returns:
            permissionDecisionReason or None
        """
        return hook_output.get("permissionDecisionReason")

    def build_result(self, messages: list[str]) -> dict | None:
        """Build PreToolUse result with allow decision.

        Args:
            messages: List of permission decision reasons

        Returns:
            Result dict with permissionDecision: allow, or None if no messages
        """
        if not messages:
            return None
        return Response.allow(" | ".join(messages[:3]))


class PostToolStrategy(ResultStrategy):
    """Strategy for PostToolUse - never terminates dispatch."""

    def should_terminate(self, result: dict, handler_name: str) -> bool:
        """PostToolUse never terminates dispatch.

        Args:
            result: Handler result dict (ignored)
            handler_name: Handler name (ignored)

        Returns:
            Always False - PostToolUse handlers cannot terminate
        """
        return False

    def extract_message(self, hook_output: dict) -> str | None:
        """Extract message from hook output.

        Args:
            hook_output: The hookSpecificOutput dict

        Returns:
            message field or None
        """
        return hook_output.get("message")

    def build_result(self, messages: list[str]) -> dict | None:
        """Build PostToolUse result from collected messages.

        Args:
            messages: List of collected messages

        Returns:
            Result dict with messages joined, or None if no messages
        """
        if not messages:
            return None
        return Response.message(" | ".join(messages[:3]), event="PostToolUse")


class NonToolStrategy(ResultStrategy):
    """Strategy for non-tool events (SessionStart, SessionEnd, Stop).

    Never terminates dispatch. Messages are returned as simple list output
    via format_output() method instead of hookSpecificOutput.
    """

    def should_terminate(self, result: dict, handler_name: str) -> bool:
        """Non-tool events never terminate dispatch.

        Returns:
            Always False
        """
        return False

    def extract_message(self, hook_output: dict) -> str | None:
        """Extract message from hook output.

        For non-tool events, messages are handled differently (string list).
        This strategy doesn't use hookSpecificOutput.

        Returns:
            None (messages handled by format_output)
        """
        return None

    def build_result(self, messages: list[str]) -> dict | None:
        """Non-tool events don't return hookSpecificOutput.

        Args:
            messages: Unused - handled by format_output()

        Returns:
            Always None - format_output() is used instead
        """
        return None


class BaseDispatcher(ABC):
    """Abstract base class for hook dispatchers."""

    # Subclasses must override these
    DISPATCHER_NAME: str = "base_dispatcher"
    HOOK_EVENT_NAME: str = "Unknown"
    ALL_HANDLERS: list[str] = []
    TOOL_HANDLERS: dict[str, list[str]] = {}
    # Handler import map: "name" -> ("module", "func") or ("module", ("fn1", "fn2", ...))
    HANDLER_IMPORTS: dict[str, tuple] = {}

    def __init__(self):
        self._validated = False
        self._handlers: dict[str, Any] = {}
        self._profile_timings: dict[str, list[float]] = {}
        self._handler_registry = HandlerRegistry()
        self._result_strategy: ResultStrategy | None = None

    @abstractmethod
    def _create_result_strategy(self) -> ResultStrategy:
        """Create the result strategy for this dispatcher.

        Each dispatcher subclass must provide its own strategy for handling
        result processing (termination, message extraction, result building).

        Returns:
            ResultStrategy instance configured for this dispatcher type
        """
        pass

    def _import_handler(self, name: str) -> Any:
        """Import and return the handler for the given name.

        Uses HANDLER_IMPORTS dict to map handler names to (module, func_spec).
        func_spec can be a string (single function) or tuple (multiple functions).

        Returns the handler callable (or tuple of callables), or None if not found.
        """
        if name not in self.HANDLER_IMPORTS:
            return None

        module_name, func_spec = self.HANDLER_IMPORTS[name]
        module = importlib.import_module(module_name)

        # Handle single function or tuple of functions
        if isinstance(func_spec, tuple):
            return tuple(getattr(module, fn) for fn in func_spec)
        return getattr(module, func_spec)

    def setup_handler_registry(self) -> None:
        """Initialize handler registry with routing rules.

        Override in subclasses to register handlers with routing rules and custom executors.
        """
        pass

    def _execute_handler(self, name: str, handler: Any, ctx: dict) -> dict | None:
        """Execute handler logic. Override for special cases.

        First checks if handler registry has a custom executor for this handler.
        If not, checks if handler registry has routing info for dual handlers.
        Otherwise calls handler(ctx) directly.

        Subclasses can override to add custom execution logic.
        """
        # Check for custom executor via registry
        if self._handler_registry.has_custom_executor(name):
            executor = self._handler_registry.get_custom_executor(name)
            return executor(name, handler, ctx)

        # Check for dual handler routing via registry
        if isinstance(handler, tuple):
            rule = self._handler_registry.routing_rules.get(name)
            if rule:
                tool_name = ctx.get("tool_name", "")
                idx = rule.tool_patterns.get(tool_name, rule.default)
                if idx < len(handler):
                    return handler[idx](ctx)
            # Default to first handler if no routing rule
            return handler[0](ctx)

        return handler(ctx)

    def get_handler(self, name: str) -> Any:
        """Lazy-load and cache handler module. Syncs with registry."""
        if name not in self._handlers:
            try:
                self._handlers[name] = self._import_handler(name)
            except ImportError as e:
                log_event(self.DISPATCHER_NAME, "import_error", {"handler": name, "error": str(e)})
                self._handlers[name] = None

        # Sync loaded handler with registry if not already registered
        handler = self._handlers.get(name)
        if handler is not None and name not in self._handler_registry.handlers:
            self._handler_registry.handlers[name] = handler

        return handler

    def validate_handlers(self) -> None:
        """Validate all handlers can be imported. Called once at startup."""
        # Initialize handler registry with routing rules
        self.setup_handler_registry()

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
        """Run a single handler with timeout protection.

        Fast handlers (in _FAST_HANDLERS) bypass the thread pool for lower latency.
        """
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
            # Fast handlers bypass thread pool (sub-10ms, no timeout risk)
            if name in _FAST_HANDLERS:
                result = self._execute_handler(name, handler, ctx)
            else:
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
        """Dispatch to appropriate handlers based on tool name.

        If TOOL_HANDLERS is empty, runs all handlers in ALL_HANDLERS (non-tool mode).
        Otherwise, routes by tool_name using TOOL_HANDLERS mapping.
        """
        # Initialize strategy on first use
        if self._result_strategy is None:
            self._result_strategy = self._create_result_strategy()

        dispatch_start = time.perf_counter()
        tool_name = ctx.get("tool_name", "")

        # Non-tool mode: empty TOOL_HANDLERS means run all handlers
        if not self.TOOL_HANDLERS:
            handlers = self.ALL_HANDLERS
            event_name = "non-tool"
        else:
            # Tool mode: route by tool_name
            handlers = self.TOOL_HANDLERS.get(tool_name, [])
            event_name = tool_name
            if not handlers:
                return None

        messages = []

        for handler_name in handlers:
            result = self.run_handler(handler_name, ctx)

            if result and isinstance(result, dict):
                hook_output = result.get("hookSpecificOutput", {})

                # Check for early termination using strategy
                if self._result_strategy.should_terminate(result, handler_name):
                    if _PROFILE_MODE:
                        print(f"[{self.DISPATCHER_NAME}] Early termination by {handler_name}",
                              file=sys.stderr)
                    return result

                # Collect message using strategy
                message = self._result_strategy.extract_message(hook_output)
                if message:
                    messages.append(message)

        # Flush any batched state writes
        write_count = flush_pending_writes()

        if _PROFILE_MODE:
            total_ms = (time.perf_counter() - dispatch_start) * 1000
            print(f"[{self.DISPATCHER_NAME}] TOTAL for {event_name}: {total_ms:.1f}ms ({len(handlers)} handlers, {write_count} writes)",
                  file=sys.stderr)

        # Build final result using strategy
        return self._result_strategy.build_result(messages)

    def run(self) -> None:
        """Main entry point - read stdin, dispatch, output result."""
        if not self._validated:
            self.validate_handlers()
            self._validated = True

        try:
            stdin_data = sys.stdin.read()
            ctx = fast_json_loads(stdin_data) if stdin_data else {}
        except Exception as e:
            # Log parse errors (always, not just in profile mode) and exit with error code
            log_event(self.DISPATCHER_NAME, "parse_error", {"error": str(e)})
            if _PROFILE_MODE:
                print(f"[{self.DISPATCHER_NAME}] stdin parse error: {e}", file=sys.stderr)
            sys.exit(1)  # Exit with error code to make failures detectable

        result = self.dispatch(ctx)
        if result:
            print(json.dumps(result))

        sys.exit(0)


# =============================================================================
# SimpleDispatcher - Base for non-tool event dispatchers
# =============================================================================

class SimpleDispatcher(ABC):
    """Base class for non-tool event dispatchers (SessionStart, SessionEnd, Stop).

    Unlike BaseDispatcher which routes by tool_name, SimpleDispatcher runs handlers
    unconditionally for their event type.

    Subclasses override:
    - DISPATCHER_NAME: Name for logging
    - EVENT_TYPE: Expected event type (or None to skip validation)
    - handle(): Process context and return messages
    - format_output(): (Optional) Custom output formatting

    Example:
        class MyDispatcher(SimpleDispatcher):
            DISPATCHER_NAME = "my_dispatcher"
            EVENT_TYPE = "SessionEnd"

            def handle(self, ctx: dict) -> list[str]:
                return ["Message 1", "Message 2"]

        if __name__ == "__main__":
            MyDispatcher().run()
    """

    DISPATCHER_NAME: str = "simple_dispatcher"
    EVENT_TYPE: str | None = None  # Set to event type to validate, or None to skip

    @abstractmethod
    def handle(self, ctx: dict) -> list[str]:
        """Process the event context and return list of messages to output.

        Args:
            ctx: Parsed JSON context from stdin

        Returns:
            List of message strings to output (can be empty)
        """
        pass

    def validate_event(self, ctx: dict) -> bool:
        """Check if this event should be handled. Override for custom validation."""
        if self.EVENT_TYPE is None:
            return True
        return ctx.get("event_type", ctx.get("event", "")) == self.EVENT_TYPE

    def format_output(self, messages: list[str]) -> str | None:
        """Format messages for output. Override for custom formatting.

        Returns:
            Formatted string to print, or None to skip output
        """
        if not messages:
            return None
        return "\n".join(messages)

    def read_context(self) -> dict:
        """Read and parse context from stdin."""
        try:
            stdin_data = sys.stdin.read()
            return fast_json_loads(stdin_data) if stdin_data else {}
        except Exception as e:
            if _PROFILE_MODE:
                print(f"[{self.DISPATCHER_NAME}] stdin parse error: {e}", file=sys.stderr)
            return {}

    @graceful_main("simple_dispatcher")
    def run(self) -> None:
        """Main entry point - read stdin, handle event, output messages."""
        ctx = self.read_context()

        if not self.validate_event(ctx):
            sys.exit(0)

        log_event(self.DISPATCHER_NAME, "dispatch", {
            "event": self.EVENT_TYPE or "unknown",
            "cwd": ctx.get("cwd", "")[:50]
        })

        messages = self.handle(ctx)
        output = self.format_output(messages)

        if output:
            print(output)

        sys.exit(0)

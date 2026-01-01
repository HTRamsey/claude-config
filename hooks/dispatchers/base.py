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
from dataclasses import dataclass
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
from hooks.hook_utils import graceful_main, log_event, is_hook_disabled, flush_pending_writes
from hooks.config import fast_json_loads


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
    def build_result(self, messages: list[str], terminated_by: str = None) -> dict | None:
        """Build final result from collected messages.

        Args:
            messages: List of collected messages from handlers
            terminated_by: Name of handler that terminated early (if any)

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

    def build_result(self, messages: list[str], terminated_by: str = None) -> dict | None:
        """Build PreToolUse result with allow decision.

        Args:
            messages: List of permission decision reasons
            terminated_by: Unused for PreToolUse

        Returns:
            Result dict with permissionDecision: allow, or None if no messages
        """
        if not messages:
            return None
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "permissionDecisionReason": " | ".join(messages[:3])
            }
        }


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

    def build_result(self, messages: list[str], terminated_by: str = None) -> dict | None:
        """Build PostToolUse result from collected messages.

        Args:
            messages: List of collected messages
            terminated_by: Unused for PostToolUse

        Returns:
            Result dict with messages joined, or None if no messages
        """
        if not messages:
            return None
        return {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "message": " | ".join(messages[:3])
            }
        }


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

    @abstractmethod
    def _import_handler(self, name: str) -> Any:
        """Import and return the handler for the given name.

        Returns the handler callable (or tuple of callables), or None if not found.
        """
        pass

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
        # Initialize strategy on first use
        if self._result_strategy is None:
            self._result_strategy = self._create_result_strategy()

        dispatch_start = time.perf_counter()
        tool_name = ctx.get("tool_name", "")

        handlers = self.TOOL_HANDLERS.get(tool_name, [])
        if not handlers:
            return None

        messages = []
        terminated_by = None

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
            print(f"[{self.DISPATCHER_NAME}] TOTAL for {tool_name}: {total_ms:.1f}ms ({len(handlers)} handlers, {write_count} writes)",
                  file=sys.stderr)

        # Build final result using strategy
        return self._result_strategy.build_result(messages, terminated_by)

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
            stdin_data = sys.stdin.read()
            ctx = fast_json_loads(stdin_data) if stdin_data else {}
        except Exception:
            sys.exit(0)

        result = self.dispatch(ctx)
        if result:
            print(json.dumps(result))

        sys.exit(0)

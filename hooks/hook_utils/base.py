"""Base classes for common hook patterns.

Provides reusable abstractions for:
- BlockingHook: PreToolUse hooks that can deny operations
- MonitoringHook: Hooks that track state without blocking
- SuggestionHook: Hooks that suggest actions/tools
"""
from abc import ABC, abstractmethod
from typing import Callable, Any

from .logging import log_event
from .state import read_state, write_state
from .session import get_session_id, read_session_state, write_session_state


class BlockingHook(ABC):
    """Base for PreToolUse hooks that can deny operations.

    Subclasses implement check() which returns deny response or None to allow.

    Example:
        class MyBlocker(BlockingHook):
            def check(self, ctx) -> dict | None:
                if some_condition(ctx):
                    return self.deny("Reason why denied")
                return None
    """

    def __init__(self, name: str):
        """Initialize blocking hook.

        Args:
            name: Hook identifier for logging
        """
        self.name = name

    @abstractmethod
    def check(self, ctx: Any) -> dict | None:
        """Check if operation should be blocked.

        Args:
            ctx: Context object (typically PreToolUseContext)

        Returns:
            Deny response dict if blocked, None to allow
        """

    def deny(self, reason: str) -> dict:
        """Build deny response.

        Args:
            reason: Human-readable reason for denial

        Returns:
            Hook response dict
        """
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason
            }
        }

    def __call__(self, ctx: Any) -> dict | None:
        """Call the hook (allows use as callable)."""
        return self.check(ctx)


class MonitoringHook(ABC):
    """Base for hooks that track state without blocking.

    Provides automatic state management via persistent storage.
    Subclasses implement process() to update state based on context.

    Example:
        class MyMonitor(MonitoringHook):
            def process(self, ctx, state: dict) -> tuple[dict, dict | None]:
                state['count'] = state.get('count', 0) + 1
                return state, None  # No response to Claude
    """

    def __init__(self, name: str, use_session: bool = False):
        """Initialize monitoring hook.

        Args:
            name: Hook identifier for logging and state file naming
            use_session: If True, use session-scoped state; else global
        """
        self.name = name
        self.use_session = use_session

    @abstractmethod
    def process(self, ctx: Any, state: dict) -> tuple[dict, dict | None]:
        """Process context and update state.

        Args:
            ctx: Context object
            state: Current state dict (loaded from storage)

        Returns:
            Tuple of (updated_state, optional_response_to_claude)
        """

    def load_state(self, ctx: Any = None) -> dict:
        """Load current state (global or session-scoped).

        Args:
            ctx: Optional context for session extraction

        Returns:
            State dict
        """
        if self.use_session:
            session_id = get_session_id(ctx) if ctx else None
            return read_session_state(self.name, session_id or "default", {})
        else:
            return read_state(self.name, {})

    def save_state(self, state: dict, ctx: Any = None) -> bool:
        """Save updated state.

        Args:
            state: State dict to save
            ctx: Optional context for session extraction

        Returns:
            True on success
        """
        if self.use_session:
            session_id = get_session_id(ctx) if ctx else None
            return write_session_state(self.name, state, session_id or "default")
        else:
            return write_state(self.name, state)

    def __call__(self, ctx: Any) -> dict | None:
        """Call the hook (allows use as callable)."""
        state = self.load_state(ctx)
        new_state, response = self.process(ctx, state)
        self.save_state(new_state, ctx)
        return response


class SuggestionHook(ABC):
    """Base for hooks that suggest actions/tools.

    Tracks what's been suggested to avoid repetition.
    Subclasses implement get_suggestion() to determine if/what to suggest.

    Example:
        class MyAdvisor(SuggestionHook):
            def get_suggestion(self, ctx) -> tuple[str, str] | None:
                key = f"skill:{ctx.tool_name}"
                if should_suggest_skill(ctx):
                    return key, f"Try the {skill_name} skill"
                return None
    """

    def __init__(self, name: str):
        """Initialize suggestion hook.

        Args:
            name: Hook identifier for logging
        """
        self.name = name
        self._suggested: set = set()

    @abstractmethod
    def get_suggestion(self, ctx: Any) -> tuple[str, str] | None:
        """Determine if a suggestion should be made.

        Args:
            ctx: Context object

        Returns:
            Tuple of (unique_key, suggestion_message), or None if no suggestion
        """

    def should_suggest(self, key: str) -> bool:
        """Check if suggestion has already been made in this session.

        Args:
            key: Unique suggestion identifier

        Returns:
            True if not yet suggested, False if already suggested
        """
        return key not in self._suggested

    def mark_suggested(self, key: str):
        """Mark a suggestion as having been made.

        Args:
            key: Unique suggestion identifier
        """
        self._suggested.add(key)

    def message(self, text: str, event: str = "PostToolUse") -> dict:
        """Build message response.

        Args:
            text: Message to send to Claude
            event: Event type (default: PostToolUse)

        Returns:
            Hook response dict
        """
        return {
            "hookSpecificOutput": {
                "hookEventName": event,
                "message": text
            }
        }

    def __call__(self, ctx: Any) -> dict | None:
        """Call the hook (allows use as callable)."""
        result = self.get_suggestion(ctx)
        if result:
            key, message = result
            if self.should_suggest(key):
                self.mark_suggested(key)
                log_event(self.name, "suggested", {"key": key})
                return self.message(message)
        return None


class StateTrackingHook(MonitoringHook):
    """Base for hooks that need fine-grained state tracking.

    Extends MonitoringHook with helpers for common patterns:
    - Tracking event counts
    - Recording timestamps
    - Incrementing counters
    - Expiring old entries

    Example:
        class MyTracker(StateTrackingHook):
            def should_track(self, ctx) -> bool:
                return ctx.tool_name == "Bash"

            def track_event(self, ctx, state: dict) -> dict:
                self.increment(state, f"bash_calls")
                return state
    """

    def __init__(self, name: str, use_session: bool = False):
        """Initialize state tracking hook.

        Args:
            name: Hook identifier
            use_session: If True, use session-scoped state
        """
        super().__init__(name, use_session)

    @abstractmethod
    def should_track(self, ctx: Any) -> bool:
        """Determine if this context should be tracked.

        Args:
            ctx: Context object

        Returns:
            True to process, False to skip
        """

    @abstractmethod
    def track_event(self, ctx: Any, state: dict) -> dict:
        """Update state based on context.

        Args:
            ctx: Context object
            state: Current state

        Returns:
            Updated state dict
        """

    def process(self, ctx: Any, state: dict) -> tuple[dict, dict | None]:
        """Default implementation delegates to subclass methods."""
        if self.should_track(ctx):
            state = self.track_event(ctx, state)
        return state, None

    @staticmethod
    def increment(state: dict, key: str, amount: int = 1) -> int:
        """Increment a counter in state.

        Args:
            state: State dict to modify
            key: Counter key (e.g. "bash_calls")
            amount: Amount to increment (default: 1)

        Returns:
            New counter value
        """
        current = state.get(key, 0)
        state[key] = current + amount
        return state[key]

    @staticmethod
    def record_timestamp(state: dict, key: str) -> str:
        """Record current timestamp in state.

        Args:
            state: State dict to modify
            key: Timestamp key (e.g. "last_call")

        Returns:
            Timestamp string (ISO format)
        """
        from datetime import datetime
        timestamp = datetime.now().isoformat()
        state[key] = timestamp
        return timestamp

    @staticmethod
    def get_count(state: dict, key: str) -> int:
        """Get counter value from state.

        Args:
            state: State dict
            key: Counter key

        Returns:
            Counter value (default 0)
        """
        return state.get(key, 0)


__all__ = [
    "BlockingHook",
    "MonitoringHook",
    "SuggestionHook",
    "StateTrackingHook",
]

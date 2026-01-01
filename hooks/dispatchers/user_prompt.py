#!/home/jonglaser/.claude/data/venv/bin/python3
"""
UserPromptSubmit Dispatcher - Consolidates all UserPromptSubmit hooks.

Benefits:
- Consolidates 2 handlers into single process
- Shared tiktoken encoder initialization
- ~50ms savings per user message

Dispatches to:
- context_manager: Check context size, warn/backup at thresholds
- usage_tracker: Track slash command usage

Extends BaseDispatcher for shared handler loading, timeout protection, and profiling.
"""
from hooks.dispatchers.base import BaseDispatcher, ResultStrategy
from hooks.hook_utils import graceful_main


class UserPromptStrategy(ResultStrategy):
    """Strategy for UserPromptSubmit - collects messages, never terminates."""

    def should_terminate(self, result: dict, handler_name: str) -> bool:
        """UserPromptSubmit never terminates dispatch."""
        return False

    def extract_message(self, hook_output: dict) -> str | None:
        """Extract message from handler output."""
        return hook_output.get("message")

    def build_result(self, messages: list[str], terminated_by: str = None) -> dict | None:
        """Build result from collected messages."""
        if not messages:
            return None
        return {"message": "\n".join(messages)}


class UserPromptDispatcher(BaseDispatcher):
    """Dispatcher for UserPromptSubmit hooks."""

    DISPATCHER_NAME = "user_prompt_dispatcher"
    HOOK_EVENT_NAME = "UserPromptSubmit"

    # All handlers run for every user prompt (no tool-based routing)
    ALL_HANDLERS = ["context_manager", "usage_tracker"]

    # No tool-based routing for UserPromptSubmit
    TOOL_HANDLERS = {}

    # Handler imports
    HANDLER_IMPORTS = {
        "context_manager": ("hooks.handlers.context_manager", "check_context"),
        "usage_tracker": ("hooks.handlers.usage_tracker", "handle"),
    }

    def _create_result_strategy(self) -> ResultStrategy:
        """Create UserPromptSubmit result strategy."""
        return UserPromptStrategy()

    def dispatch(self, ctx: dict) -> dict | None:
        """Dispatch to all UserPromptSubmit handlers.

        Overrides base dispatch() since UserPromptSubmit has no tool routing.
        All handlers run unconditionally.
        """
        if self._result_strategy is None:
            self._result_strategy = self._create_result_strategy()

        messages = []

        for handler_name in self.ALL_HANDLERS:
            result = self.run_handler(handler_name, ctx)

            if result and isinstance(result, dict):
                # Handle both direct message and hookSpecificOutput formats
                message = result.get("message")
                if not message:
                    hook_output = result.get("hookSpecificOutput", {})
                    message = self._result_strategy.extract_message(hook_output)

                if message:
                    messages.append(message)

        return self._result_strategy.build_result(messages)


# Create dispatcher instance
_dispatcher = UserPromptDispatcher()


@graceful_main("user_prompt_dispatcher")
def main():
    _dispatcher.run()


if __name__ == "__main__":
    main()

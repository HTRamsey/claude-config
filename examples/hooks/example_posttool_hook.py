#!/home/jonglaser/.claude/data/venv/bin/python3
"""Example PostToolUse hook - Log tool execution metrics.

This is a minimal example showing the structure of a PostToolUse hook.
PostToolUse hooks react AFTER a tool runs - they cannot block.

Usage in settings.json:
{
  "hooks": {
    "PostToolUse": [{
      "matcher": "Bash",
      "hooks": [{"command": "~/.claude/hooks/your_hook.py"}]
    }]
  }
}
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "hooks"))
try:
    from hook_utils import graceful_main, log_event
except ImportError:
    def graceful_main(name):
        def decorator(fn):
            return fn
        return decorator
    def log_event(*args, **kwargs):
        pass


def log_execution(ctx: dict) -> dict | None:
    """Log tool execution for metrics."""
    tool_name = ctx.get("tool_name", "unknown")
    tool_input = ctx.get("tool_input", {})
    tool_result = ctx.get("tool_result", {})

    # Example: log command execution time
    if tool_name == "Bash":
        command = tool_input.get("command", "")[:50]
        # stdout/stderr may be in tool_result
        log_event("metrics", "bash_complete", {"command": command})

    # PostToolUse hooks can provide feedback but cannot block
    # Return None or a message to display
    return None


@graceful_main("example_posttool_hook")
def main():
    try:
        ctx = json.load(sys.stdin)
    except (json.JSONDecodeError, Exception):
        sys.exit(0)

    result = log_execution(ctx)
    if result:
        print(json.dumps(result))

    sys.exit(0)


if __name__ == "__main__":
    main()

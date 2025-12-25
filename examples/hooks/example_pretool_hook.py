#!/home/jonglaser/.claude/venv/bin/python3
"""Example PreToolUse hook - Block writes to protected paths.

This is a minimal example showing the structure of a PreToolUse hook.
Copy and modify for your own hooks.

Usage in settings.json:
{
  "hooks": {
    "PreToolUse": [{
      "matcher": "Write|Edit",
      "hooks": [{"command": "~/.claude/hooks/your_hook.py"}]
    }]
  }
}
"""
import json
import sys
from pathlib import Path

# Import shared utilities (optional but recommended)
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "hooks"))
try:
    from hook_utils import graceful_main, log_event
except ImportError:
    # Fallback if hook_utils not available
    def graceful_main(name):
        def decorator(fn):
            return fn
        return decorator
    def log_event(*args, **kwargs):
        pass


# Your hook logic
PROTECTED_PATHS = [".env", "secrets/", "credentials"]


def check_protected(ctx: dict) -> dict | None:
    """Check if tool targets a protected path."""
    tool_input = ctx.get("tool_input", {})
    file_path = tool_input.get("file_path", "")

    for pattern in PROTECTED_PATHS:
        if pattern in file_path:
            log_event("example_hook", "blocked", {"path": file_path})
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": f"Protected path: {pattern}"
                }
            }
    return None


@graceful_main("example_pretool_hook")
def main():
    try:
        ctx = json.load(sys.stdin)
    except (json.JSONDecodeError, Exception):
        sys.exit(0)

    result = check_protected(ctx)
    if result:
        print(json.dumps(result))

    sys.exit(0)


if __name__ == "__main__":
    main()

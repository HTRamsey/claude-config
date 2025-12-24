#!/home/jonglaser/.claude/venv/bin/python3
"""Block edits to commonly protected files.

PreToolUse hook for Write/Edit tools.
Input format: {"tool_name": "Edit", "tool_input": {"file_path": "/path/to/file"}}
"""
import json
import sys
from pathlib import Path

# Import shared utilities
sys.path.insert(0, str(Path(__file__).parent))
try:
    from hook_utils import graceful_main, log_event
    HAS_UTILS = True
except ImportError:
    HAS_UTILS = False
    def graceful_main(name):
        def decorator(func):
            return func
        return decorator
    def log_event(*args, **kwargs):
        pass


@graceful_main("file_protection")
def main():
    try:
        ctx = json.load(sys.stdin)
    except (json.JSONDecodeError, Exception):
        sys.exit(0)

    # Extract file_path from tool_input (PreToolUse format)
    tool_input = ctx.get("tool_input", {})
    file_path = tool_input.get("file_path", "")

    # Generic protected patterns (adjust per project in project's .claude/hooks)
    protected = [
        ".git/",
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        ".env",
        "credentials",
        "secrets",
    ]

    if file_path and any(p in file_path.lower() for p in protected):
        log_event("file_protection", "blocked", {"file": file_path})
        result = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": f"Blocked edit to protected file: {file_path}"
            }
        }
        print(json.dumps(result))
        sys.exit(0)

    sys.exit(0)

if __name__ == "__main__":
    main()

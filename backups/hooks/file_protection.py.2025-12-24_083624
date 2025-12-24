#!/home/jonglaser/.claude/venv/bin/python3
"""Block access to sensitive files (Read/Write/Edit).

PreToolUse hook for Read, Write, and Edit tools.
Enforces protection that glob patterns in settings.json can't provide on Linux.
"""
import fnmatch
import json
import os
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


# Patterns that block both read and write
PROTECTED_PATTERNS = [
    # Environment and secrets
    ".env",
    ".env.*",
    "*/.env",
    "*/.env.*",
    "*/secrets/*",
    "*secrets*",
    "*credentials*",

    # Private keys and certificates
    "*.pem",
    "*.key",
    "*.p12",
    "*.pfx",
    "*id_rsa*",

    # SSH/Cloud config
    "*/.ssh/*",
    "*/.aws/*",
    "*/.config/gcloud/*",

    # Auth tokens and configs
    "*token*",
    "*/.npmrc",
    "*/.pypirc",
    "*/.netrc",
    "*/.docker/config.json",
    "*/.kube/config",

    # Git internals (allow read, block write)
    # Handled separately below
]

# Patterns only blocked for write/edit (not read)
WRITE_ONLY_PATTERNS = [
    ".git/*",
    "*/.git/*",
    "package-lock.json",
    "*/package-lock.json",
    "yarn.lock",
    "*/yarn.lock",
    "pnpm-lock.yaml",
    "*/pnpm-lock.yaml",
]


def matches_any(filepath: str, patterns: list) -> str | None:
    """Check if filepath matches any pattern. Returns matching pattern or None."""
    # Normalize path
    filepath = os.path.normpath(filepath)
    filename = os.path.basename(filepath)

    for pattern in patterns:
        # Check against full path
        if fnmatch.fnmatch(filepath, pattern):
            return pattern
        # Check against filename only
        if fnmatch.fnmatch(filename, pattern):
            return pattern
        # Check if pattern appears as substring (for simple patterns)
        if not any(c in pattern for c in '*?['):
            if pattern in filepath:
                return pattern
    return None


def check_file_protection(ctx: dict) -> dict | None:
    """Handler function for dispatcher. Returns result dict or None."""
    tool_name = ctx.get("tool_name", "")
    tool_input = ctx.get("tool_input", {})
    file_path = tool_input.get("file_path", "")

    if not file_path:
        return None

    # Expand home directory
    if file_path.startswith("~"):
        file_path = os.path.expanduser(file_path)

    is_write = tool_name in ("Write", "Edit")

    # Check protected patterns (block read and write)
    matched = matches_any(file_path, PROTECTED_PATTERNS)
    if matched:
        action = "write to" if is_write else "read"
        log_event("file_protection", "blocked", {
            "file": file_path,
            "pattern": matched,
            "tool": tool_name
        })
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": f"Blocked {action} protected file: {file_path} (matches: {matched})"
            }
        }

    # Check write-only patterns (only block write/edit, allow read)
    if is_write:
        matched = matches_any(file_path, WRITE_ONLY_PATTERNS)
        if matched:
            log_event("file_protection", "blocked", {
                "file": file_path,
                "pattern": matched,
                "tool": tool_name
            })
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": f"Blocked write to protected file: {file_path} (matches: {matched})"
                }
            }

    return None


@graceful_main("file_protection")
def main():
    try:
        ctx = json.load(sys.stdin)
    except (json.JSONDecodeError, Exception):
        sys.exit(0)

    result = check_file_protection(ctx)
    if result:
        print(json.dumps(result))

    sys.exit(0)


if __name__ == "__main__":
    main()

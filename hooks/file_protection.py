#!/home/jonglaser/.claude/venv/bin/python3
"""Block access to sensitive files (Read/Write/Edit).

PreToolUse hook for Read, Write, and Edit tools.
Enforces protection that glob patterns in settings.json can't provide on Linux.

Uses hook_sdk for typed context and response builders.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from hook_sdk import (
    PreToolUseContext,
    Response,
    Patterns,
    dispatch_handler,
    run_standalone,
    expand_path,
    log_event,
)


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


@dispatch_handler("file_protection", event="PreToolUse")
def check_file_protection(ctx: PreToolUseContext) -> dict | None:
    """
    Handler function for dispatcher.

    Args:
        ctx: PreToolUseContext with typed access to tool_name, tool_input, etc.

    Returns:
        Response dict if blocked, None if allowed
    """
    file_path = ctx.tool_input.file_path
    if not file_path:
        return None

    # Expand and normalize path
    file_path = expand_path(file_path)
    is_write = ctx.is_write or ctx.is_edit

    # Check protected patterns (block read and write)
    matched = Patterns.matches_glob(file_path, PROTECTED_PATTERNS)
    if matched:
        action = "write to" if is_write else "read"
        log_event("file_protection", "blocked", {
            "file": file_path,
            "pattern": matched,
            "tool": ctx.tool_name
        })
        return Response.deny(
            f"Blocked {action} protected file: {file_path} (matches: {matched})"
        )

    # Check write-only patterns (only block write/edit, allow read)
    if is_write:
        matched = Patterns.matches_glob(file_path, WRITE_ONLY_PATTERNS)
        if matched:
            log_event("file_protection", "blocked", {
                "file": file_path,
                "pattern": matched,
                "tool": ctx.tool_name
            })
            return Response.deny(
                f"Blocked write to protected file: {file_path} (matches: {matched})"
            )

    return None


if __name__ == "__main__":
    # Standalone mode: read from stdin, write to stdout
    run_standalone(lambda raw: check_file_protection(raw))

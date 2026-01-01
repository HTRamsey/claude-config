#!/home/jonglaser/.claude/data/venv/bin/python3
"""Block access to sensitive files (Read/Write/Edit).

PreToolUse hook for Read, Write, and Edit tools.
Enforces protection that glob patterns in settings.json can't provide on Linux.

Uses BlockingHook base class for cleaner code.
"""
from hooks.hook_sdk import (
    PreToolUseContext,
    Patterns,
    dispatch_handler,
    log_event,
    BlockingHook,
)
from hooks.hook_utils import expand_path
from hooks.config import ProtectedFiles


class FileProtectionHook(BlockingHook):
    """Block access to sensitive files."""

    def check(self, ctx: PreToolUseContext) -> dict | None:
        """Check if file operation should be blocked."""
        file_path = ctx.tool_input.file_path
        if not file_path:
            return None

        # Expand and normalize path
        file_path = expand_path(file_path)
        is_write = ctx.is_write or ctx.is_edit

        # Check allowlist first (overrides protection)
        for allowed in ProtectedFiles.ALLOWED_PATHS:
            allowed_expanded = expand_path(allowed)
            if file_path == allowed_expanded:
                return None

        # Check protected patterns (block read and write)
        matched = Patterns.matches_glob(file_path, ProtectedFiles.PROTECTED_PATTERNS)
        if matched:
            action = "write to" if is_write else "read"
            log_event("file_protection", "blocked", {
                "file": file_path,
                "pattern": matched,
                "tool": ctx.tool_name
            })
            return self.deny(
                f"Blocked {action} protected file: {file_path} (matches: {matched})"
            )

        # Check write-only patterns (only block write/edit, allow read)
        if is_write:
            matched = Patterns.matches_glob(file_path, ProtectedFiles.WRITE_ONLY_PATTERNS)
            if matched:
                log_event("file_protection", "blocked", {
                    "file": file_path,
                    "pattern": matched,
                    "tool": ctx.tool_name
                })
                return self.deny(
                    f"Blocked write to protected file: {file_path} (matches: {matched})"
                )

        return None


# Create hook instance for dispatcher
_hook = FileProtectionHook("file_protection")


@dispatch_handler("file_protection", event="PreToolUse")
def check_file_protection(ctx: PreToolUseContext) -> dict | None:
    """Handler function for dispatcher."""
    return _hook(ctx)

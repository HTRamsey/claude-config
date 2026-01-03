#!/home/jonglaser/.claude/data/venv/bin/python3
"""Block access to sensitive files (Read/Write/Edit).

PreToolUse hook for Read, Write, and Edit tools.
Enforces protection that glob patterns in settings.json can't provide on Linux.

Uses BlockingHook base class for cleaner code.
"""
# Handler metadata for dispatcher auto-discovery
APPLIES_TO = ["Read", "Write", "Edit"]
from hooks.hook_sdk import (
    PreToolUseContext,
    Patterns,
    dispatch_handler,
    log_event,
    BlockingHook,
)
from hooks.hook_utils import normalize_path
from hooks.config import (
    get_protected_patterns_compiled,
    get_write_only_patterns_compiled,
    get_allowed_patterns_compiled,
)


class FileProtectionHook(BlockingHook):
    """Block access to sensitive files."""

    def check(self, ctx: PreToolUseContext) -> dict | None:
        """Check if file operation should be blocked.

        Security: Uses normalize_path() which resolves symlinks to prevent
        symlink-based bypasses (e.g., ln -s .env safe_link && cat safe_link).
        """
        file_path = ctx.tool_input.file_path
        if not file_path:
            return None

        # Normalize path and resolve symlinks to prevent bypass attacks
        file_path = normalize_path(file_path)
        is_write = ctx.is_write or ctx.is_edit

        # Check allowlist first (overrides protection)
        if Patterns.find_matching_pattern(file_path, get_allowed_patterns_compiled()):
            return None

        # Check protected patterns (block read and write)
        matched = Patterns.find_matching_pattern(file_path, get_protected_patterns_compiled())
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
            matched = Patterns.find_matching_pattern(file_path, get_write_only_patterns_compiled())
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

#!/home/jonglaser/.claude/venv/bin/python3
"""Smart Permission Auto-Approvals.

PermissionRequest hook that auto-approves safe operations based on patterns.
This reduces permission prompts for common, safe operations.
"""
import json
import re
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

# Auto-approve patterns for Read operations
READ_AUTO_APPROVE = [
    # Documentation
    r'\.md$',
    r'\.txt$',
    r'\.rst$',
    r'README',
    r'LICENSE',
    r'CHANGELOG',
    r'CONTRIBUTING',
    # Config files (non-sensitive)
    r'\.json$',
    r'\.yaml$',
    r'\.yml$',
    r'\.toml$',
    r'\.ini$',
    r'\.cfg$',
    # Test files
    r'test[_/]',
    r'_test\.',
    r'\.test\.',
    r'\.spec\.',
    r'__tests__/',
    r'tests/',
    # Type definitions
    r'\.d\.ts$',
    r'\.pyi$',
    # Lock files (read-only)
    r'package-lock\.json$',
    r'yarn\.lock$',
    r'pnpm-lock\.yaml$',
    r'Cargo\.lock$',
    r'poetry\.lock$',
    r'Pipfile\.lock$',
]

# Auto-approve patterns for Edit/Write to test files
WRITE_AUTO_APPROVE = [
    r'test[_/]',
    r'_test\.',
    r'\.test\.',
    r'\.spec\.',
    r'__tests__/',
    r'tests/',
    r'fixtures/',
    r'mocks/',
    r'__mocks__/',
]

# Never auto-approve these (deny patterns take precedence)
NEVER_AUTO_APPROVE = [
    r'\.env',
    r'secrets?',
    r'credentials?',
    r'password',
    r'\.pem$',
    r'\.key$',
    r'id_rsa',
    r'\.ssh/',
    r'\.aws/',
    r'\.git/',
]


def matches_any(path: str, patterns: list) -> bool:
    """Check if path matches any pattern."""
    path_lower = path.lower()
    return any(re.search(p, path_lower, re.IGNORECASE) for p in patterns)


@graceful_main("smart_permissions")
def main():
    try:
        ctx = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = ctx.get("tool_name", "")
    tool_input = ctx.get("tool_input", {})
    file_path = tool_input.get("file_path", "")

    if not file_path:
        sys.exit(0)

    # Never auto-approve sensitive files
    if matches_any(file_path, NEVER_AUTO_APPROVE):
        sys.exit(0)

    should_approve = False
    reason = ""

    if tool_name == "Read":
        if matches_any(file_path, READ_AUTO_APPROVE):
            should_approve = True
            reason = "Auto-approved: safe file type for reading"

    elif tool_name in ("Edit", "Write"):
        if matches_any(file_path, WRITE_AUTO_APPROVE):
            should_approve = True
            reason = "Auto-approved: test/fixture file"

    if should_approve:
        log_event("smart_permissions", "auto_approved", {"tool": tool_name, "file": file_path})
        result = {
            "hookSpecificOutput": {
                "hookEventName": "PermissionRequest",
                "decision": {
                    "behavior": "allow"
                },
                "permissionDecisionReason": reason
            }
        }
        print(json.dumps(result))

    sys.exit(0)


if __name__ == "__main__":
    main()

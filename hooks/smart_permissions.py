#!/home/jonglaser/.claude/data/venv/bin/python3
"""Smart Permission Auto-Approvals with Learning.

PermissionRequest hook that auto-approves safe operations based on:
1. Static patterns (known-safe file types)
2. Learned patterns (user consistently approves)

Learning: PostToolUse tracks successful executions. After N approvals
for a pattern (tool + directory), it's added to auto-approve list.
"""
import json
import re
import sys
from datetime import datetime
from pathlib import Path

# Import shared utilities
sys.path.insert(0, str(Path(__file__).parent))
from hook_utils import graceful_main, log_event

# Learned patterns file
PATTERNS_FILE = Path.home() / ".claude" / "data" / "permission-patterns.json"

# Approval threshold before auto-approving a pattern
APPROVAL_THRESHOLD = 3

# Auto-approve patterns for Read operations (static)
READ_AUTO_APPROVE = [
    r'\.md$', r'\.txt$', r'\.rst$',
    r'README', r'LICENSE', r'CHANGELOG', r'CONTRIBUTING',
    r'\.json$', r'\.yaml$', r'\.yml$', r'\.toml$', r'\.ini$', r'\.cfg$',
    r'test[_/]', r'_test\.', r'\.test\.', r'\.spec\.', r'__tests__/', r'tests/',
    r'\.d\.ts$', r'\.pyi$',
    r'package-lock\.json$', r'yarn\.lock$', r'pnpm-lock\.yaml$',
    r'Cargo\.lock$', r'poetry\.lock$', r'Pipfile\.lock$',
]

# Auto-approve patterns for Edit/Write (static)
WRITE_AUTO_APPROVE = [
    r'test[_/]', r'_test\.', r'\.test\.', r'\.spec\.',
    r'__tests__/', r'tests/', r'fixtures/', r'mocks/', r'__mocks__/',
]

# Never auto-approve (deny patterns take precedence)
NEVER_AUTO_APPROVE = [
    r'\.env', r'secrets?', r'credentials?', r'password',
    r'\.pem$', r'\.key$', r'id_rsa', r'\.ssh/', r'\.aws/', r'\.git/',
]


def matches_any(path: str, patterns: list) -> bool:
    """Check if path matches any pattern."""
    path_lower = path.lower()
    return any(re.search(p, path_lower, re.IGNORECASE) for p in patterns)


def load_patterns() -> dict:
    """Load learned patterns from file."""
    if not PATTERNS_FILE.exists():
        return {"patterns": {}, "updated": None}
    try:
        with open(PATTERNS_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {"patterns": {}, "updated": None}


def save_patterns(data: dict):
    """Save learned patterns to file."""
    data["updated"] = datetime.now().isoformat()
    PATTERNS_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(PATTERNS_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    except IOError:
        pass


def normalize_path(path: str) -> str:
    """Normalize path to directory pattern for learning."""
    p = Path(path)
    # Get parent directory, normalized
    parent = str(p.parent)
    # Expand home
    if parent.startswith(str(Path.home())):
        parent = "~" + parent[len(str(Path.home())):]
    return parent


def get_pattern_key(tool: str, path: str) -> str:
    """Create a pattern key from tool and path."""
    directory = normalize_path(path)
    # Get file extension or type
    ext = Path(path).suffix or "noext"
    return f"{tool}:{directory}:{ext}"


def record_approval(tool: str, path: str):
    """Record an approved operation (called from PostToolUse)."""
    if matches_any(path, NEVER_AUTO_APPROVE):
        return  # Never learn sensitive file patterns

    key = get_pattern_key(tool, path)
    data = load_patterns()

    if key not in data["patterns"]:
        data["patterns"][key] = {"count": 0, "first_seen": datetime.now().isoformat()}

    data["patterns"][key]["count"] += 1
    data["patterns"][key]["last_seen"] = datetime.now().isoformat()

    # Log if we just reached threshold
    count = data["patterns"][key]["count"]
    if count == APPROVAL_THRESHOLD:
        log_event("smart_permissions", "pattern_learned", {"key": key, "count": count})

    save_patterns(data)


def check_learned_patterns(tool: str, path: str) -> bool:
    """Check if operation matches a learned auto-approve pattern."""
    key = get_pattern_key(tool, path)
    data = load_patterns()

    pattern = data.get("patterns", {}).get(key)
    if pattern and pattern.get("count", 0) >= APPROVAL_THRESHOLD:
        return True

    # Also check parent directories (learned patterns propagate up slightly)
    directory = normalize_path(path)
    ext = Path(path).suffix or "noext"

    # Check one level up
    parent_dir = str(Path(directory).parent)
    parent_key = f"{tool}:{parent_dir}:{ext}"
    parent_pattern = data.get("patterns", {}).get(parent_key)
    if parent_pattern and parent_pattern.get("count", 0) >= APPROVAL_THRESHOLD * 2:
        return True  # Require double threshold for parent dir patterns

    return False


def smart_permissions_post(ctx: dict) -> dict | None:
    """PostToolUse handler - record successful operations for learning."""
    tool_name = ctx.get("tool_name", "")
    if tool_name not in ("Read", "Edit", "Write"):
        return None

    tool_input = ctx.get("tool_input", {})
    file_path = tool_input.get("file_path", "")

    if not file_path:
        return None

    # Record this approval (tool executed = user approved)
    record_approval(tool_name, file_path)
    return None


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

    # Check static patterns
    if tool_name == "Read":
        if matches_any(file_path, READ_AUTO_APPROVE):
            should_approve = True
            reason = "Auto-approved: safe file type for reading"

    elif tool_name in ("Edit", "Write"):
        if matches_any(file_path, WRITE_AUTO_APPROVE):
            should_approve = True
            reason = "Auto-approved: test/fixture file"

    # Check learned patterns if static didn't match
    if not should_approve and check_learned_patterns(tool_name, file_path):
        should_approve = True
        reason = "Auto-approved: learned pattern (user consistently approves)"
        log_event("smart_permissions", "learned_auto_approved", {"tool": tool_name, "file": file_path})

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

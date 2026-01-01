#!/home/jonglaser/.claude/data/venv/bin/python3
"""Smart Permission Auto-Approvals with Learning.

PermissionRequest hook that auto-approves safe operations based on:
1. Static patterns (known-safe file types)
2. Learned patterns (user consistently approves)

Learning: PostToolUse tracks successful executions. After N approvals
for a pattern (tool + directory), it's added to auto-approve list.

Uses cachetools TTLCache for automatic cache expiration.
"""
import json
import re
import sys
from datetime import datetime
from pathlib import Path

from cachetools import TTLCache

# Import shared utilities
from hook_utils import graceful_main, log_event
from hook_sdk import PostToolUseContext, PreToolUseContext, Response
from config import DATA_DIR, Thresholds, SmartPermissions

# Learned patterns file
PATTERNS_FILE = DATA_DIR / "permission-patterns.json"

# Approval threshold before auto-approving a pattern (from centralized config)
APPROVAL_THRESHOLD = Thresholds.PERMISSION_APPROVAL_THRESHOLD

# Use lazy-compiled patterns from config
def get_read_patterns():
    return SmartPermissions.get_read()

def get_write_patterns():
    return SmartPermissions.get_write()

def get_never_patterns():
    return SmartPermissions.get_never()


def matches_any(path: str, patterns: list) -> bool:
    """Check if path matches any pre-compiled pattern."""
    path_lower = path.lower()
    return any(p.search(path_lower) for p in patterns)


# TTL cache for learned patterns (5-second TTL, single entry)
_PATTERNS_CACHE_TTL = 5.0
_patterns_cache: TTLCache = TTLCache(maxsize=1, ttl=_PATTERNS_CACHE_TTL)
_PATTERNS_CACHE_KEY = "patterns"


def load_patterns() -> dict:
    """Load learned patterns from file with caching."""
    if _PATTERNS_CACHE_KEY in _patterns_cache:
        return _patterns_cache[_PATTERNS_CACHE_KEY]

    if not PATTERNS_FILE.exists():
        data = {"patterns": {}, "updated": None}
    else:
        try:
            with open(PATTERNS_FILE) as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError):
            data = {"patterns": {}, "updated": None}

    _patterns_cache[_PATTERNS_CACHE_KEY] = data
    return data


def save_patterns(data: dict):
    """Save learned patterns to file and update cache."""
    data["updated"] = datetime.now().isoformat()
    PATTERNS_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(PATTERNS_FILE, 'w') as f:
            json.dump(data, f, indent=2)
        # Update cache
        _patterns_cache[_PATTERNS_CACHE_KEY] = data
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
    if matches_any(path, get_never_patterns()):
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


def smart_permissions_post(raw: dict) -> dict | None:
    """PostToolUse handler - record successful operations for learning."""
    ctx = PostToolUseContext(raw)

    if ctx.tool_name not in ("Read", "Edit", "Write"):
        return None

    file_path = ctx.tool_input.file_path
    if not file_path:
        return None

    # Record this approval (tool executed = user approved)
    record_approval(ctx.tool_name, file_path)
    return None


@graceful_main("smart_permissions")
def main():
    try:
        raw = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    ctx = PreToolUseContext(raw)
    file_path = ctx.tool_input.file_path

    if not file_path:
        sys.exit(0)

    # Never auto-approve sensitive files
    if matches_any(file_path, get_never_patterns()):
        sys.exit(0)

    should_approve = False
    reason = ""

    # Check static patterns
    if ctx.tool_name == "Read":
        if matches_any(file_path, get_read_patterns()):
            should_approve = True
            reason = "Auto-approved: safe file type for reading"

    elif ctx.tool_name in ("Edit", "Write"):
        if matches_any(file_path, get_write_patterns()):
            should_approve = True
            reason = "Auto-approved: test/fixture file"

    # Check learned patterns if static didn't match
    if not should_approve and check_learned_patterns(ctx.tool_name, file_path):
        should_approve = True
        reason = "Auto-approved: learned pattern (user consistently approves)"
        log_event("smart_permissions", "learned_auto_approved", {"tool": ctx.tool_name, "file": file_path})

    if should_approve:
        log_event("smart_permissions", "auto_approved", {"tool": ctx.tool_name, "file": file_path})
        result = Response.allow(reason)
        print(json.dumps(result))

    sys.exit(0)


if __name__ == "__main__":
    main()

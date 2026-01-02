#!/home/jonglaser/.claude/data/venv/bin/python3
"""
PermissionRequest Dispatcher - Smart auto-approvals with learning.

Handlers:
- Static patterns: Known-safe file types (test files, docs, configs)
- Learned patterns: User consistently approves → auto-approve

Also provides PostToolUse handler (smart_permissions_post) for learning.
Uses cache abstraction for automatic cache expiration.
"""
import json
import sys
from pathlib import Path

# Import shared utilities
from hooks.hook_utils import graceful_main, log_event, get_timestamp, safe_load_json, atomic_write_json, create_ttl_cache
from hooks.hook_sdk import PostToolUseContext, PreToolUseContext, Response, Patterns
from hooks.config import DATA_DIR, Thresholds, Timeouts, Limits, SmartPermissions

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


# TTL cache for learned patterns (from centralized config)
_patterns_cache = create_ttl_cache(maxsize=Limits.PATTERNS_CACHE_MAXSIZE, ttl=Timeouts.PATTERNS_CACHE_TTL)
_PATTERNS_CACHE_KEY = "patterns"


def load_patterns() -> dict:
    """Load learned patterns from file with caching."""
    if _PATTERNS_CACHE_KEY in _patterns_cache:
        return _patterns_cache[_PATTERNS_CACHE_KEY]

    data = safe_load_json(PATTERNS_FILE, {"patterns": {}, "updated": None})
    _patterns_cache[_PATTERNS_CACHE_KEY] = data
    return data


def save_patterns(data: dict):
    """Save learned patterns to file and update cache."""
    data["updated"] = get_timestamp()
    if atomic_write_json(PATTERNS_FILE, data):
        # Update cache
        _patterns_cache[_PATTERNS_CACHE_KEY] = data


def get_parent_pattern(path: str) -> str:
    """Get parent directory pattern for permission learning.

    Note: Different from hook_utils.io.normalize_path which resolves to absolute path.
    This returns a pattern suitable for permission matching.
    """
    p = Path(path)
    # Get parent directory, normalized
    parent = str(p.parent)
    # Expand home
    if parent.startswith(str(Path.home())):
        parent = "~" + parent[len(str(Path.home())):]
    return parent


def get_pattern_key(tool: str, path: str) -> str:
    """Create a pattern key from tool and path."""
    directory = get_parent_pattern(path)
    # Get file extension or type
    ext = Path(path).suffix or "noext"
    return f"{tool}:{directory}:{ext}"


def record_approval(tool: str, path: str):
    """Record an approved operation (called from PostToolUse)."""
    if Patterns.matches_compiled(path, get_never_patterns()):
        return  # Never learn sensitive file patterns

    key = get_pattern_key(tool, path)
    data = load_patterns()

    if key not in data["patterns"]:
        data["patterns"][key] = {"count": 0, "first_seen": get_timestamp()}

    data["patterns"][key]["count"] += 1
    data["patterns"][key]["last_seen"] = get_timestamp()

    # Log if we just reached threshold
    count = data["patterns"][key]["count"]
    if count == APPROVAL_THRESHOLD:
        log_event("smart_permissions", "pattern_learned", {"key": key, "count": count})

    save_patterns(data)


def check_learned_patterns(tool: str, path: str) -> bool:
    """Check if operation matches a learned auto-approve pattern."""
    key = get_pattern_key(tool, path)
    data = load_patterns()
    patterns = data.get("patterns", {})

    # Check direct pattern match
    pattern = patterns.get(key)
    if pattern and pattern.get("count", 0) >= APPROVAL_THRESHOLD:
        return True

    # Check parent directory pattern (require double threshold)
    directory = get_parent_pattern(path)
    ext = Path(path).suffix or "noext"
    parent_dir = str(Path(directory).parent)
    parent_key = f"{tool}:{parent_dir}:{ext}"
    parent_pattern = patterns.get(parent_key)

    return bool(parent_pattern and parent_pattern.get("count", 0) >= APPROVAL_THRESHOLD * 2)


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
    except json.JSONDecodeError as e:
        log_event("smart_permissions", "parse_error", {"error": str(e)})
        sys.exit(1)  # Exit with error code to make failures detectable

    ctx = PreToolUseContext(raw)
    file_path = ctx.tool_input.file_path

    if not file_path:
        sys.exit(0)

    # Never auto-approve sensitive files
    if Patterns.matches_compiled(file_path, get_never_patterns()):
        sys.exit(0)

    should_approve = False
    reason = ""

    # Check static patterns
    if ctx.tool_name == "Read":
        if Patterns.matches_compiled(file_path, get_read_patterns()):
            should_approve = True
            reason = "Auto-approved: safe file type for reading"

    elif ctx.tool_name in ("Edit", "Write"):
        if Patterns.matches_compiled(file_path, get_write_patterns()):
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

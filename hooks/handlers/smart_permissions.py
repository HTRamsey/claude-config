"""
Smart Permissions handler - Permission learning and auto-approval.

Provides:
- Pattern matching for safe file types (static patterns)
- Learning from user approvals (dynamic patterns)
- PostToolUse recording of approvals

Used by:
- dispatchers/permission.py (PermissionRequest event)
- dispatchers/post_tool.py (PostToolUse event)
"""
import re
from pathlib import Path

from hooks.hook_sdk import PostToolUseContext, HookHandler, Patterns
from hooks.hook_utils import log_event, get_timestamp, safe_load_json, atomic_write_json, create_ttl_cache
from hooks.config import DATA_DIR, Thresholds, Timeouts, Limits, SmartPermissions

# Handler metadata for dispatcher auto-discovery
APPLIES_TO = ["Read", "Edit", "Write"]

# Learned patterns file
PATTERNS_FILE = DATA_DIR / "permission-patterns.json"

# Approval threshold before auto-approving a pattern
APPROVAL_THRESHOLD = Thresholds.PERMISSION_APPROVAL_THRESHOLD

# TTL cache for learned patterns
_patterns_cache = create_ttl_cache(maxsize=Limits.PATTERNS_CACHE_MAXSIZE, ttl=Timeouts.PATTERNS_CACHE_TTL)
_PATTERNS_CACHE_KEY = "patterns"


# =============================================================================
# Pattern accessors (lazy-compiled from config)
# =============================================================================

def get_read_patterns() -> list[re.Pattern]:
    """Get compiled read auto-approve patterns."""
    return SmartPermissions.get_read()


def get_write_patterns() -> list[re.Pattern]:
    """Get compiled write auto-approve patterns."""
    return SmartPermissions.get_write()


def get_never_patterns() -> list[re.Pattern]:
    """Get compiled never-approve patterns."""
    return SmartPermissions.get_never()


# =============================================================================
# Pattern storage
# =============================================================================

def load_patterns() -> dict:
    """Load learned patterns from file with caching."""
    if _PATTERNS_CACHE_KEY in _patterns_cache:
        return _patterns_cache[_PATTERNS_CACHE_KEY]

    data = safe_load_json(PATTERNS_FILE, {"patterns": {}, "updated": None})
    _patterns_cache[_PATTERNS_CACHE_KEY] = data
    return data


def save_patterns(data: dict) -> None:
    """Save learned patterns to file and update cache."""
    data["updated"] = get_timestamp()
    if atomic_write_json(PATTERNS_FILE, data):
        _patterns_cache[_PATTERNS_CACHE_KEY] = data


# =============================================================================
# Pattern utilities
# =============================================================================

def get_parent_pattern(path: str) -> str:
    """Get parent directory pattern for permission learning."""
    p = Path(path)
    parent = str(p.parent)
    if parent.startswith(str(Path.home())):
        parent = "~" + parent[len(str(Path.home())):]
    return parent


def get_pattern_key(tool: str, path: str) -> str:
    """Create a pattern key from tool and path."""
    directory = get_parent_pattern(path)
    ext = Path(path).suffix or "noext"
    return f"{tool}:{directory}:{ext}"


# =============================================================================
# Learning logic
# =============================================================================

def record_approval(tool: str, path: str) -> None:
    """Record an approved operation (called from PostToolUse)."""
    if Patterns.matches_compiled(path, get_never_patterns()):
        return  # Never learn sensitive file patterns

    key = get_pattern_key(tool, path)
    data = load_patterns()

    if key not in data["patterns"]:
        data["patterns"][key] = {"count": 0, "first_seen": get_timestamp()}

    data["patterns"][key]["count"] += 1
    data["patterns"][key]["last_seen"] = get_timestamp()

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


# =============================================================================
# Auto-approval check (for PermissionRequest dispatcher)
# =============================================================================

def check_auto_approve(tool_name: str, file_path: str) -> tuple[bool, str]:
    """Check if a file operation should be auto-approved.

    Args:
        tool_name: The tool being used (Read, Edit, Write)
        file_path: Path to the file

    Returns:
        (should_approve, reason) tuple
    """
    if not file_path:
        return False, ""

    # Never auto-approve sensitive files
    if Patterns.matches_compiled(file_path, get_never_patterns()):
        return False, ""

    # Check static patterns
    if tool_name == "Read":
        if Patterns.matches_compiled(file_path, get_read_patterns()):
            return True, "Auto-approved: safe file type for reading"

    elif tool_name in ("Edit", "Write"):
        if Patterns.matches_compiled(file_path, get_write_patterns()):
            return True, "Auto-approved: test/fixture file"

    # Check learned patterns
    if check_learned_patterns(tool_name, file_path):
        log_event("smart_permissions", "learned_auto_approved", {"tool": tool_name, "file": file_path})
        return True, "Auto-approved: learned pattern (user consistently approves)"

    return False, ""


# =============================================================================
# PostToolUse handler (for recording approvals)
# =============================================================================

class SmartPermissionsHandler(HookHandler):
    """Record file operations for permission learning."""

    name = "smart_permissions"
    tools = ["Read", "Edit", "Write"]
    event = "PostToolUse"

    def handle(self, ctx: PostToolUseContext) -> dict | None:
        """Record successful file operation for learning."""
        file_path = ctx.tool_input.file_path
        if not file_path:
            return None

        # Never learn sensitive file patterns
        if Patterns.matches_compiled(file_path, get_never_patterns()):
            return None

        # Record this approval (tool executed = user approved)
        record_approval(ctx.tool_name, file_path)
        return None


# Handler instance for dispatcher
_handler = SmartPermissionsHandler()


def smart_permissions_post(raw: dict) -> dict | None:
    """Handler function for PostToolUse dispatcher."""
    return _handler(raw)


def handle_permission_request(raw: dict) -> dict | None:
    """Handle PermissionRequest event - check for auto-approval.

    Args:
        raw: Raw context dict with tool_name, tool_input

    Returns:
        Response.allow() dict if should auto-approve, None otherwise
    """
    from hooks.hook_sdk import PreToolUseContext, Response

    ctx = PreToolUseContext(raw)
    file_path = ctx.tool_input.file_path

    should_approve, reason = check_auto_approve(ctx.tool_name, file_path)

    if should_approve:
        log_event("smart_permissions", "auto_approved", {"tool": ctx.tool_name, "file": file_path})
        return Response.allow(reason)

    return None

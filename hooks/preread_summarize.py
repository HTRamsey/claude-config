#!/home/jonglaser/.claude/venv/bin/python3
"""
Pre-Read Summarization Hook - Intercepts large file reads.
Suggests using quick-lookup agent or smart-preview.sh for files >200 lines before full read.

Returns modification to use summarization for large files.
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

# Configuration
LARGE_FILE_LINES = 200  # Suggest summarization above this
LARGE_FILE_BYTES = 15000  # ~200 lines * 75 chars
ALWAYS_SUMMARIZE_EXTENSIONS = {'.log', '.csv', '.json', '.xml', '.yaml', '.yml'}
SKIP_EXTENSIONS = {'.md', '.txt', '.ini', '.cfg', '.env'}  # Usually need full content

def count_lines_fast(file_path: Path) -> int:
    """Fast line count using buffer reading."""
    try:
        with open(file_path, 'rb') as f:
            return sum(1 for _ in f)
    except Exception:
        return 0

def should_summarize(file_path: str, limit: int | None) -> tuple[bool, str]:
    """Determine if file should be summarized first."""
    path = Path(file_path)

    if not path.exists():
        return False, ""

    # Skip if user already specified a limit
    if limit and limit < LARGE_FILE_LINES:
        return False, ""

    ext = path.suffix.lower()

    # Skip certain file types
    if ext in SKIP_EXTENSIONS:
        return False, ""

    # Check file size first (faster than line count)
    try:
        size = path.stat().st_size
    except Exception:
        return False, ""

    if size < LARGE_FILE_BYTES:
        return False, ""

    # For large files, count lines
    lines = count_lines_fast(path)

    if lines <= LARGE_FILE_LINES:
        return False, ""

    # Build reason
    size_kb = size / 1024
    reason = f"{lines} lines, {size_kb:.1f}KB"

    if ext in ALWAYS_SUMMARIZE_EXTENSIONS:
        reason += f" ({ext} file - consider extracting specific fields)"

    return True, reason

@graceful_main("preread_summarize")
def main():
    try:
        ctx = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = ctx.get("tool_name", "")
    tool_input = ctx.get("tool_input", {})

    if tool_name != "Read":
        sys.exit(0)

    file_path = tool_input.get("file_path", "")
    limit = tool_input.get("limit")

    if not file_path:
        sys.exit(0)

    should, reason = should_summarize(file_path, limit)

    if should:
        filename = Path(file_path).name
        result = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "permissionDecisionReason": f"[Large File] {filename}: {reason}\n  → Consider: Task(quick-lookup) or smart-preview.sh first\n  → Or add limit parameter to read specific section"
            }
        }
        print(json.dumps(result))

    sys.exit(0)

if __name__ == "__main__":
    main()

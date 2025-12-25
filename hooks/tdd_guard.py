#!/home/jonglaser/.claude/venv/bin/python3
"""TDD Guard - Warns about implementation files without corresponding tests.

PreToolUse hook for Write/Edit tools.
Encourages test-driven development by reminding about tests.

Warning escalation: After 3 warnings in a session, blocks until test exists.
Set TDD_GUARD_STRICT=1 to always block (no warnings).
Set TDD_GUARD_WARN_ONLY=1 to never block (warnings only).
"""
import json
import os
import sys
import time
from pathlib import Path

# Import shared utilities
sys.path.insert(0, str(Path(__file__).parent))
from hook_utils import graceful_main, log_event

# Escalation settings
WARNING_THRESHOLD = 3  # Block after this many warnings
WARNING_WINDOW = 3600  # 1 hour window for counting warnings
DATA_DIR = Path(__file__).parent.parent / "data"
WARNING_FILE = DATA_DIR / "tdd-warnings.json"


def find_test_file(impl_path: Path) -> bool:
    """Check if a test file exists for the implementation."""
    name = impl_path.stem
    suffix = impl_path.suffix
    parent = impl_path.parent

    test_patterns = [
        parent / f"test_{name}{suffix}",
        parent / f"{name}_test{suffix}",
        parent / "tests" / f"test_{name}{suffix}",
        parent / "tests" / f"{name}_test{suffix}",
        parent.parent / "tests" / f"test_{name}{suffix}",
        parent.parent / "tests" / f"{name}_test{suffix}",
    ]

    if suffix in {'.js', '.ts', '.jsx', '.tsx'}:
        base = name.replace('.test', '').replace('.spec', '')
        test_patterns.extend([
            parent / f"{base}.test{suffix}",
            parent / f"{base}.spec{suffix}",
            parent / "__tests__" / f"{base}.test{suffix}",
            parent / "__tests__" / f"{base}.spec{suffix}",
        ])

    return any(p.exists() for p in test_patterns)


# Constants for check_tdd
CODE_EXTENSIONS = {'.py', '.js', '.ts', '.jsx', '.tsx', '.go', '.rs', '.java', '.rb'}
TEST_PATTERNS = ['test_', '_test', '.test.', '.spec.', 'tests/', 'test/', '__tests__/']
SKIP_PATTERNS = [
    '__init__', 'conftest', 'setup', 'config', 'settings',
    'migrations/', 'scripts/', 'hooks/', 'commands/', 'skills/', 'agents/',
    'utils/', 'helpers/', 'types/', 'models/', 'interfaces/', 'schemas/',
    'examples/', 'fixtures/', 'mocks/', 'stubs/', 'constants/', 'enums/',
    'webpack', 'vite', 'rollup', 'babel', 'eslint', 'prettier',
]
MIN_LINES_FOR_TDD = 30


def load_warnings() -> dict:
    """Load warning counts from file."""
    if not WARNING_FILE.exists():
        return {"warnings": [], "updated": time.time()}
    try:
        with open(WARNING_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {"warnings": [], "updated": time.time()}


def save_warnings(data: dict) -> None:
    """Save warning counts to file."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    data["updated"] = time.time()
    with open(WARNING_FILE, "w") as f:
        json.dump(data, f, indent=2)


def count_recent_warnings(data: dict) -> int:
    """Count warnings within the time window."""
    now = time.time()
    cutoff = now - WARNING_WINDOW
    recent = [w for w in data.get("warnings", []) if w.get("time", 0) > cutoff]
    data["warnings"] = recent  # Prune old warnings
    return len(recent)


def add_warning(data: dict, file_path: str) -> int:
    """Add a warning and return total count."""
    data.setdefault("warnings", []).append({
        "file": file_path,
        "time": time.time()
    })
    save_warnings(data)
    return count_recent_warnings(data)


def check_tdd(ctx: dict) -> dict | None:
    """Handler function for dispatcher. Returns result dict or None."""
    tool_input = ctx.get("tool_input", {})
    file_path = tool_input.get("file_path", "")

    if not file_path:
        return None

    path = Path(file_path)

    # Skip non-code files
    if path.suffix not in CODE_EXTENSIONS:
        return None

    # Skip test files themselves
    path_str = str(path).lower()
    if any(p in path_str for p in TEST_PATTERNS):
        return None

    # Skip config, setup, utility, and low-test-value files
    if any(p in path_str for p in SKIP_PATTERNS):
        return None

    # Only enforce for new files (skip existing files)
    if path.exists():
        return None

    # Check content size - skip small files
    content = tool_input.get("content", "") or tool_input.get("new_string", "")
    line_count = content.count('\n') + 1 if content else 0
    if line_count < MIN_LINES_FOR_TDD:
        return None

    # Check if test exists
    if not find_test_file(path):
        # Check environment overrides
        strict_mode = os.environ.get("TDD_GUARD_STRICT", "0") == "1"
        warn_only = os.environ.get("TDD_GUARD_WARN_ONLY", "0") == "1"

        # Load and count warnings
        warning_data = load_warnings()
        warning_count = count_recent_warnings(warning_data)

        # Determine action: block or warn
        should_block = strict_mode or (warning_count >= WARNING_THRESHOLD and not warn_only)

        if should_block:
            log_event("tdd_guard", "block", {
                "file": path.name,
                "lines": line_count,
                "warnings": warning_count
            })
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": (
                        f"[TDD] Blocked: No test for {path.name} ({line_count} lines). "
                        f"Write a test first, or set TDD_GUARD_WARN_ONLY=1 to disable blocking."
                    )
                }
            }
        else:
            # Add warning and inform user
            new_count = add_warning(warning_data, file_path)
            remaining = WARNING_THRESHOLD - new_count
            log_event("tdd_guard", "warning", {
                "file": path.name,
                "lines": line_count,
                "count": new_count,
                "remaining": remaining
            })
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "allow",
                    "permissionDecisionReason": (
                        f"[TDD] Warning {new_count}/{WARNING_THRESHOLD}: No test for {path.name} "
                        f"({line_count} lines) - write tests first. "
                        f"{'Will block after ' + str(remaining) + ' more.' if remaining > 0 else 'Next time will block.'}"
                    )
                }
            }

    return None


@graceful_main("tdd_guard")
def main():
    try:
        ctx = json.load(sys.stdin)
    except (json.JSONDecodeError, Exception):
        sys.exit(0)

    result = check_tdd(ctx)
    if result:
        print(json.dumps(result))

    sys.exit(0)


if __name__ == "__main__":
    main()

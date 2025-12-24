#!/home/jonglaser/.claude/venv/bin/python3
"""TDD Guard - Warns about implementation files without corresponding tests.

PreToolUse hook for Write/Edit tools.
Encourages test-driven development by reminding about tests.
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
        log_event("tdd_guard", "warning", {"file": path.name, "lines": line_count})
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "permissionDecisionReason": f"[TDD] No test for {path.name} ({line_count} lines) - consider writing tests first"
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

#!/home/jonglaser/.claude/data/venv/bin/python3
"""TDD Guard - Warns about implementation files without corresponding tests.

PreToolUse hook for Write/Edit tools.
Encourages test-driven development by reminding about tests.

Warning escalation: After 3 warnings in a session, blocks until test exists.
Set TDD_GUARD_STRICT=1 to always block (no warnings).
Set TDD_GUARD_WARN_ONLY=1 to never block (warnings only).
"""
import os
import sys
import time
from pathlib import Path

# Import SDK for typed context and response builders
from hook_sdk import (
    PreToolUseContext,
    Response,
    dispatch_handler,
    run_standalone,
    log_event,
    read_state,
    write_state,
    DATA_DIR,
)
from config import Timeouts, Thresholds, FilePatterns

# Escalation settings
WARNING_THRESHOLD = Thresholds.TDD_WARNING_THRESHOLD
WARNING_WINDOW = Timeouts.WARNING_WINDOW
WARNING_STATE_KEY = "tdd-warnings"


def get_test_paths(impl_path: Path) -> list[Path]:
    """Generate all possible test file paths for an implementation file.

    Uses unified patterns that match both TEST_PATTERNS (for identification)
    and actual test file locations (for existence checking).
    """
    name = impl_path.stem
    suffix = impl_path.suffix
    parent = impl_path.parent

    paths = [
        # Standard patterns: test_ prefix and _test suffix
        parent / f"test_{name}{suffix}",
        parent / f"{name}_test{suffix}",
        # Tests subdirectory
        parent / "tests" / f"test_{name}{suffix}",
        parent / "tests" / f"{name}_test{suffix}",
        parent / "test" / f"test_{name}{suffix}",
        parent / "test" / f"{name}_test{suffix}",
        # Parent tests directory
        parent.parent / "tests" / f"test_{name}{suffix}",
        parent.parent / "tests" / f"{name}_test{suffix}",
    ]

    # JavaScript/TypeScript specific: .test. and .spec. patterns
    if suffix in {'.js', '.ts', '.jsx', '.tsx'}:
        base = name.replace('.test', '').replace('.spec', '')
        paths.extend([
            parent / f"{base}.test{suffix}",
            parent / f"{base}.spec{suffix}",
            parent / "__tests__" / f"{base}.test{suffix}",
            parent / "__tests__" / f"{base}.spec{suffix}",
        ])

    return paths


def find_test_file(impl_path: Path) -> bool:
    """Check if a test file exists for the implementation."""
    return any(p.exists() for p in get_test_paths(impl_path))


# Use config for constants
CODE_EXTENSIONS = FilePatterns.CODE_EXTENSIONS
TEST_PATTERNS = FilePatterns.TEST_PATTERNS
SKIP_PATTERNS = FilePatterns.TDD_SKIP_PATTERNS
MIN_LINES_FOR_TDD = Thresholds.MIN_LINES_FOR_TDD


def load_warnings() -> dict:
    """Load warning counts using SDK state management (has built-in caching)."""
    return read_state(WARNING_STATE_KEY, {"warnings": [], "updated": time.time()})


def save_warnings(data: dict) -> None:
    """Save warning counts using SDK state management."""
    data["updated"] = time.time()
    write_state(WARNING_STATE_KEY, data)


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


@dispatch_handler("tdd_guard", event="PreToolUse")
def check_tdd(ctx: PreToolUseContext) -> dict | None:
    """Handler function for dispatcher. Returns result dict or None."""
    file_path = ctx.tool_input.file_path

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
    content = ctx.tool_input.content or ctx.tool_input.new_string
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
            return Response.deny(
                f"[TDD] Blocked: No test for {path.name} ({line_count} lines). "
                f"Write a test first, or set TDD_GUARD_WARN_ONLY=1 to disable blocking."
            )
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
            return Response.allow(
                f"[TDD] Warning {new_count}/{WARNING_THRESHOLD}: No test for {path.name} "
                f"({line_count} lines) - write tests first. "
                f"{'Will block after ' + str(remaining) + ' more.' if remaining > 0 else 'Next time will block.'}"
            )

    return None


if __name__ == "__main__":
    # Standalone mode: read from stdin, write to stdout
    run_standalone(lambda raw: check_tdd(raw))

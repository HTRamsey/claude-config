#!/home/jonglaser/.claude/data/venv/bin/python3
"""Detect potential credentials/API keys before git commit.

PreToolUse hook for Bash tool - triggers on git commit commands.
Scans staged content for patterns that look like API keys, passwords, tokens, etc.
"""
import subprocess

from hooks.hook_utils import log_event
from hooks.config import Credentials
from hooks.hook_sdk import Response


def get_compiled_patterns():
    """Get compiled patterns from config."""
    return Credentials.get_compiled_patterns()


def is_allowlisted(file_path: str) -> bool:
    """Check if file is in allowlist (test files, examples, etc.)"""
    path_lower = file_path.lower()
    return any(pattern in path_lower for pattern in Credentials.allowlist_patterns)


def scan_for_sensitive(content: str) -> list:
    """Scan content for potential sensitive data, return list of (pattern_name, match)"""
    findings = []
    for compiled, name in get_compiled_patterns():
        # Use search() first for quick detection, findall() only if match exists
        if compiled.search(content):
            matches = compiled.findall(content)
            for match in matches[:3]:  # Limit to 3 per pattern
                if isinstance(match, tuple):
                    match = match[0]
                truncated = match[:20] + "..." if len(match) > 20 else match
                findings.append((name, truncated))
    return findings


def get_staged_diff() -> tuple[str, list[str]]:
    """Get staged diff content and list of staged files."""
    try:
        # Get staged diff
        result = subprocess.run(
            ["git", "diff", "--cached", "--no-color"],
            capture_output=True,
            text=True,
            timeout=5
        )
        diff_content = result.stdout

        # Get list of staged files
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True,
            text=True,
            timeout=5
        )
        staged_files = [f for f in result.stdout.strip().split("\n") if f]

        return diff_content, staged_files
    except (subprocess.TimeoutExpired, subprocess.SubprocessError):
        return "", []


def handle(raw: dict) -> dict:
    """Scan staged changes for credentials before commit."""
    tool_input = raw.get("tool_input", {})
    command = tool_input.get("command", "")

    # Only trigger on git commit commands
    if not command.strip().startswith("git commit"):
        return None

    # Get staged content
    diff_content, staged_files = get_staged_diff()

    if not diff_content:
        return None

    # Filter out allowlisted files from consideration
    non_allowlisted = [f for f in staged_files if not is_allowlisted(f)]
    if not non_allowlisted:
        return None

    # Scan for sensitive data
    findings = scan_for_sensitive(diff_content)

    if findings:
        unique_types = list(set(name for name, _ in findings))[:5]
        log_event("credential_scanner", "blocked", {
            "types": unique_types,
            "files": non_allowlisted[:3]
        }, "warning")

        return Response.deny(
            f"Potential credentials detected: {', '.join(unique_types)}. "
            f"Files: {', '.join(non_allowlisted[:3])}. Review with: git diff --cached"
        )

    return None

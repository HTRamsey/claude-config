"""
Git context handler - shared git utilities for session dispatchers.

Provides git status, branch info, and context summaries used by:
- session_start.py (context display)
- stop.py (uncommitted changes check)
"""
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any


def run_cmd(cmd: list, cwd: str = None, timeout: int = 5) -> str:
    """Run command and return output, or empty string on failure."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd)
        return result.stdout.strip() if result.returncode == 0 else ""
    except Exception:
        return ""


def is_git_repo(cwd: str = None) -> bool:
    """Check if directory is a git repository."""
    return bool(run_cmd(["git", "rev-parse", "--git-dir"], cwd))


def get_branch(cwd: str = None) -> str:
    """Get current branch name."""
    return run_cmd(["git", "branch", "--show-current"], cwd)


def get_recent_commits(cwd: str = None, count: int = 3) -> str:
    """Get recent commit summaries."""
    return run_cmd(["git", "log", "--oneline", f"-{count}", "--no-decorate"], cwd)


def get_status(cwd: str = None) -> dict[str, Any]:
    """Get comprehensive git status.

    Returns:
        Dict with keys:
        - is_git_repo: bool
        - branch: str
        - has_staged: bool
        - has_unstaged: bool
        - has_untracked: bool
        - ahead: int (commits ahead of upstream)
        - file_count: int
    """
    result = {
        "is_git_repo": False,
        "branch": "",
        "has_staged": False,
        "has_unstaged": False,
        "has_untracked": False,
        "ahead": 0,
        "file_count": 0,
    }

    if not is_git_repo(cwd):
        return result

    result["is_git_repo"] = True
    result["branch"] = get_branch(cwd)

    # Parse porcelain status
    status_output = run_cmd(["git", "status", "--porcelain"], cwd)
    if status_output:
        lines = status_output.split('\n')
        result["file_count"] = len(lines)

        for line in lines:
            if len(line) < 2:
                continue
            index, worktree = line[0], line[1]

            if index not in (' ', '?'):
                result["has_staged"] = True
            if worktree not in (' ', '?'):
                result["has_unstaged"] = True
            if '?' in (index, worktree):
                result["has_untracked"] = True

    # Check commits ahead of upstream
    ahead_output = run_cmd(["git", "rev-list", "--count", "@{upstream}..HEAD"], cwd)
    if ahead_output:
        try:
            result["ahead"] = int(ahead_output)
        except ValueError:
            pass

    return result


def get_context_summary(cwd: str = None) -> list[str]:
    """Get formatted git context for session start display.

    Uses parallel execution for git commands.

    Returns:
        List of formatted strings for display.
    """
    if not is_git_repo(cwd):
        return []

    git_commands = {
        "branch": ["git", "branch", "--show-current"],
        "commits": ["git", "log", "--oneline", "-3", "--no-decorate"],
        "status": ["git", "status", "--short"],
    }

    results = {}
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(run_cmd, cmd, cwd): name for name, cmd in git_commands.items()}
        for future in as_completed(futures, timeout=5):
            name = futures[future]
            try:
                results[name] = future.result()
            except Exception:
                results[name] = ""

    context = []

    if branch := results.get("branch"):
        context.append(f"Branch: {branch}")

    if commits := results.get("commits"):
        context.append(f"Recent commits:\n{commits}")

    if status := results.get("status"):
        lines = status.split('\n')
        if len(lines) > 5:
            context.append(f"Uncommitted: {len(lines)} files changed")
        else:
            context.append(f"Uncommitted:\n{status}")

    return context

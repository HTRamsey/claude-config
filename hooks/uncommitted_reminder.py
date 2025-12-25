#!/home/jonglaser/.claude/venv/bin/python3
"""Remind about uncommitted changes at session end.

Stop hook that checks for uncommitted git changes and reminds the user.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

# Import shared utilities
sys.path.insert(0, str(Path(__file__).parent))
from hook_utils import graceful_main, log_event

def get_git_status(cwd: str = None) -> dict:
    """Get git status for the working directory"""
    result = {
        "is_git_repo": False,
        "has_staged": False,
        "has_unstaged": False,
        "has_untracked": False,
        "branch": "",
        "ahead": 0,
        "file_count": 0,
    }

    try:
        # Check if in git repo
        check = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=5
        )
        if check.returncode != 0:
            return result

        result["is_git_repo"] = True

        # Get branch name
        branch = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=5
        )
        result["branch"] = branch.stdout.strip()

        # Get status
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=5
        )

        if status.returncode == 0:
            lines = status.stdout.strip().split('\n') if status.stdout.strip() else []
            result["file_count"] = len(lines)

            for line in lines:
                if not line:
                    continue
                index = line[0] if len(line) > 0 else ' '
                worktree = line[1] if len(line) > 1 else ' '

                if index != ' ' and index != '?':
                    result["has_staged"] = True
                if worktree != ' ' and worktree != '?':
                    result["has_unstaged"] = True
                if index == '?' or worktree == '?':
                    result["has_untracked"] = True

        # Check if ahead of remote
        ahead = subprocess.run(
            ["git", "rev-list", "--count", "@{upstream}..HEAD"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=5
        )
        if ahead.returncode == 0:
            result["ahead"] = int(ahead.stdout.strip() or 0)

    except (subprocess.TimeoutExpired, subprocess.SubprocessError, ValueError):
        pass

    return result

@graceful_main("uncommitted_reminder")
def main():
    try:
        ctx = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    # Get working directory from context
    cwd = ctx.get("cwd") or ctx.get("working_directory") or os.getcwd()

    status = get_git_status(cwd)

    if not status["is_git_repo"]:
        sys.exit(0)

    messages = []

    if status["has_staged"] or status["has_unstaged"]:
        msg_parts = []
        if status["has_staged"]:
            msg_parts.append("staged")
        if status["has_unstaged"]:
            msg_parts.append("unstaged")
        messages.append(f"Uncommitted changes ({', '.join(msg_parts)}) in {status['file_count']} files")

    if status["ahead"] > 0:
        messages.append(f"Branch '{status['branch']}' is {status['ahead']} commits ahead of remote (unpushed)")

    if status["has_untracked"] and status["file_count"] <= 10:
        messages.append("Untracked files present")

    if messages:
        print("[Uncommitted Changes] Before ending session:")
        for msg in messages:
            print(f"  - {msg}")
        if status["has_staged"] or status["has_unstaged"]:
            print("  Consider: git commit -m 'WIP: <description>'")
        if status["ahead"] > 0:
            print("  Consider: git push")

    sys.exit(0)

if __name__ == "__main__":
    main()

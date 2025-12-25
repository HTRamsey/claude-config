#!/home/jonglaser/.claude/venv/bin/python3
"""
Session Start Hook - Auto-loads context at the start of a new session.

Runs on UserPromptSubmit. Detects first message of a session and outputs:
- Git branch and recent commits
- Uncommitted changes summary
- TODO.md if present
- Recent errors from logs

This gives Claude immediate context without manual prompting.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

# Import shared utilities
sys.path.insert(0, str(Path(__file__).parent))
from hook_utils import graceful_main, log_event, is_new_session, read_stdin_context


def run_cmd(cmd: list, cwd: str = None) -> str:
    """Run command and return output, or empty string on failure."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=5,
            cwd=cwd
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except Exception:
        return ""

def get_git_context(cwd: str) -> list:
    """Get git branch, recent commits, and status."""
    context = []

    # Check if in git repo
    if not run_cmd(["git", "rev-parse", "--git-dir"], cwd):
        return context

    # Current branch
    branch = run_cmd(["git", "branch", "--show-current"], cwd)
    if branch:
        context.append(f"Branch: {branch}")

    # Recent commits (last 3)
    commits = run_cmd([
        "git", "log", "--oneline", "-3", "--no-decorate"
    ], cwd)
    if commits:
        context.append(f"Recent commits:\n{commits}")

    # Uncommitted changes summary
    status = run_cmd(["git", "status", "--short"], cwd)
    if status:
        lines = status.split('\n')
        if len(lines) > 5:
            context.append(f"Uncommitted: {len(lines)} files changed")
        else:
            context.append(f"Uncommitted:\n{status}")

    return context

def get_todo_context(cwd: str) -> str:
    """Check for TODO.md and return first few lines."""
    todo_paths = [
        Path(cwd) / "TODO.md",
        Path(cwd) / "todo.md",
        Path(cwd) / ".claude" / "TODO.md",
    ]

    for todo_path in todo_paths:
        if todo_path.exists():
            try:
                with open(todo_path) as f:
                    lines = f.readlines()[:10]
                    content = ''.join(lines).strip()
                    if content:
                        return f"TODO.md:\n{content}"
            except Exception:
                pass

    return ""

def get_recent_errors() -> str:
    """Check hook logs for recent errors."""
    log_file = Path.home() / ".claude" / "data" / "hook-events.jsonl"
    if not log_file.exists():
        return ""

    try:
        errors = []
        with open(log_file) as f:
            # Read last 100 lines
            lines = f.readlines()[-100:]
            for line in lines:
                try:
                    entry = json.loads(line)
                    if entry.get("level") == "error":
                        errors.append(f"{entry.get('hook')}: {entry.get('data', {}).get('msg', 'unknown')}")
                except json.JSONDecodeError:
                    continue

        if errors:
            recent = errors[-3:]  # Last 3 errors
            return f"Recent hook errors: {', '.join(recent)}"
    except Exception:
        pass

    return ""


def get_usage_summary() -> str:
    """Get compact usage stats for today."""
    from datetime import datetime, timedelta

    parts = []
    today = datetime.now().strftime("%Y-%m-%d")

    # Count sessions today (files modified in last 24h)
    projects_dir = Path.home() / ".claude" / "projects"
    if projects_dir.exists():
        try:
            yesterday = datetime.now() - timedelta(days=1)
            session_count = 0
            for jsonl in projects_dir.rglob("*.jsonl"):
                try:
                    if datetime.fromtimestamp(jsonl.stat().st_mtime) > yesterday:
                        session_count += 1
                except Exception:
                    continue
            if session_count > 0:
                parts.append(f"Sessions (24h): {session_count}")
        except Exception:
            pass

    # Get agent/skill usage from usage-stats.json
    usage_file = Path.home() / ".claude" / "data" / "usage-stats.json"
    if usage_file.exists():
        try:
            with open(usage_file) as f:
                usage = json.load(f)

            daily = usage.get("daily", {}).get(today, {})
            agent_count = daily.get("agents", 0)
            skill_count = daily.get("skills", 0)
            cmd_count = daily.get("commands", 0)

            if agent_count or skill_count or cmd_count:
                usage_parts = []
                if agent_count:
                    usage_parts.append(f"{agent_count} agents")
                if skill_count:
                    usage_parts.append(f"{skill_count} skills")
                if cmd_count:
                    usage_parts.append(f"{cmd_count} commands")
                parts.append(f"Today: {', '.join(usage_parts)}")

            # Top agent if any
            agents = usage.get("agents", {})
            if agents:
                top_agent = max(agents.items(), key=lambda x: x[1].get("count", 0))
                if top_agent[1].get("count", 0) > 2:
                    parts.append(f"Top agent: {top_agent[0]} ({top_agent[1]['count']}x)")
        except Exception:
            pass

    return ", ".join(parts) if parts else ""

@graceful_main("session_start")
def main():
    ctx = read_stdin_context()
    transcript_path = ctx.get('transcript_path', '')
    cwd = ctx.get('cwd', os.getcwd())

    # SessionStart event fires once per session, no need for is_new_session check
    log_event("session_start", "new_session", {"cwd": cwd})

    # Gather context
    output_parts = ["[Session Start]"]

    # Git context
    git_ctx = get_git_context(cwd)
    if git_ctx:
        output_parts.extend(git_ctx)

    # TODO.md
    todo_ctx = get_todo_context(cwd)
    if todo_ctx:
        output_parts.append(todo_ctx)

    # Usage summary (sessions, agents, skills today)
    usage = get_usage_summary()
    if usage:
        output_parts.append(usage)

    # Output if we have context
    if len(output_parts) > 1:
        print('\n'.join(output_parts))

    sys.exit(0)

if __name__ == "__main__":
    main()

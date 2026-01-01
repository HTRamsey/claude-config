#!/home/jonglaser/.claude/data/venv/bin/python3
"""
Session Start Hook - Auto-loads context at the start of a new session.

Runs on SessionStart. Outputs:
- Git branch and recent commits
- Uncommitted changes summary
- TODO.md if present
- Recent errors from logs

This gives Claude immediate context without manual prompting.
Uses ThreadPoolExecutor to run git commands in parallel for faster startup.
"""
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# Import shared utilities
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
    """Get git branch, recent commits, and status using parallel execution."""
    # Check if in git repo first (fast check)
    if not run_cmd(["git", "rev-parse", "--git-dir"], cwd):
        return []

    # Run git commands in parallel
    git_commands = {
        "branch": ["git", "branch", "--show-current"],
        "commits": ["git", "log", "--oneline", "-3", "--no-decorate"],
        "status": ["git", "status", "--short"],
    }

    results = {}
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(run_cmd, cmd, cwd): name
            for name, cmd in git_commands.items()
        }
        for future in as_completed(futures, timeout=5):
            name = futures[future]
            try:
                results[name] = future.result()
            except Exception:
                results[name] = ""

    # Build context from results
    context = []

    branch = results.get("branch", "")
    if branch:
        context.append(f"Branch: {branch}")

    commits = results.get("commits", "")
    if commits:
        context.append(f"Recent commits:\n{commits}")

    status = results.get("status", "")
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


def get_codebase_map(cwd: str, max_depth: int = 3) -> str:
    """Generate concise project structure map.

    Returns a tree-like structure of the codebase, excluding common
    build/vendor directories. Limited to max_depth levels.
    """
    IGNORE_DIRS = {
        'node_modules', 'vendor', 'build', 'dist', '__pycache__',
        '.git', '.svn', '.hg', 'target', 'out', 'bin', 'obj',
        'venv', '.venv', 'env', '.env', 'coverage', '.cache',
        '.tox', '.pytest_cache', '.mypy_cache', 'htmlcov',
    }
    IGNORE_PATTERNS = {'.min.js', '.min.css', '.map', '.lock'}

    def should_ignore(name: str) -> bool:
        if name in IGNORE_DIRS:
            return True
        for pattern in IGNORE_PATTERNS:
            if name.endswith(pattern):
                return True
        return False

    def build_tree(path: Path, depth: int = 0, prefix: str = "") -> list:
        if depth > max_depth:
            return []

        lines = []
        try:
            entries = sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
        except PermissionError:
            return []

        # Filter entries
        entries = [e for e in entries if not should_ignore(e.name) and not e.name.startswith('.')]

        # Limit entries per level
        max_entries = 15 if depth == 0 else 10
        show_more = len(entries) > max_entries
        entries = entries[:max_entries]

        for i, entry in enumerate(entries):
            is_last = (i == len(entries) - 1) and not show_more
            connector = "└── " if is_last else "├── "
            child_prefix = "    " if is_last else "│   "

            if entry.is_dir():
                lines.append(f"{prefix}{connector}{entry.name}/")
                lines.extend(build_tree(entry, depth + 1, prefix + child_prefix))
            else:
                lines.append(f"{prefix}{connector}{entry.name}")

        if show_more:
            lines.append(f"{prefix}└── ... and more")

        return lines

    try:
        cwd_path = Path(cwd)
        if not cwd_path.exists():
            return ""

        tree_lines = build_tree(cwd_path)
        if not tree_lines:
            return ""

        # Add project name as root
        project_name = cwd_path.name
        return f"Project: {project_name}/\n" + "\n".join(tree_lines)
    except Exception:
        return ""


def detect_project_type(cwd: str) -> str:
    """Detect project type based on config files."""
    indicators = {
        "package.json": "Node.js",
        "Cargo.toml": "Rust",
        "pyproject.toml": "Python",
        "setup.py": "Python",
        "go.mod": "Go",
        "pom.xml": "Java/Maven",
        "build.gradle": "Java/Gradle",
        "CMakeLists.txt": "C/C++ (CMake)",
        "Makefile": "Make",
        "Gemfile": "Ruby",
        "composer.json": "PHP",
        "mix.exs": "Elixir",
        "pubspec.yaml": "Dart/Flutter",
    }

    cwd_path = Path(cwd)
    detected = []

    for file, lang in indicators.items():
        if (cwd_path / file).exists():
            detected.append(lang)

    if detected:
        return f"Type: {', '.join(detected[:3])}"
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

    # Git context (runs branch/commits/status in parallel)
    git_ctx = get_git_context(cwd)
    if git_ctx:
        output_parts.extend(git_ctx)

    # Usage summary (sessions, agents, skills today)
    usage = get_usage_summary()
    if usage:
        output_parts.append(usage)

    # Project type detection
    project_type = detect_project_type(cwd)
    if project_type:
        output_parts.append(project_type)

    # Codebase map (only for non-home directories to avoid huge output)
    home = str(Path.home())
    if cwd != home and not cwd.startswith(home + "/."):
        codebase_map = get_codebase_map(cwd, max_depth=2)
        if codebase_map:
            output_parts.append(codebase_map)

    # TODO.md
    todo_ctx = get_todo_context(cwd)
    if todo_ctx:
        output_parts.append(todo_ctx)

    # Output if we have context
    if len(output_parts) > 1:
        print('\n'.join(output_parts))

    sys.exit(0)

if __name__ == "__main__":
    main()

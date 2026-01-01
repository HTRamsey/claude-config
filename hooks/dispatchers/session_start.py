#!/home/jonglaser/.claude/data/venv/bin/python3
"""
SessionStart Dispatcher - Consolidates all SessionStart hooks.

Handlers:
- session_context: Git context, project type, usage stats
- start_viewer: Launch claude-code-viewer if not running
"""
import json
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path

from hooks.dispatchers.base import SimpleDispatcher
from hooks.hook_utils import log_event


# =============================================================================
# Git Context Handler
# =============================================================================

def run_cmd(cmd: list, cwd: str = None) -> str:
    """Run command and return output, or empty string on failure."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5, cwd=cwd)
        return result.stdout.strip() if result.returncode == 0 else ""
    except Exception:
        return ""


def get_git_context(cwd: str) -> list:
    """Get git branch, recent commits, and status using parallel execution."""
    if not run_cmd(["git", "rev-parse", "--git-dir"], cwd):
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


def detect_project_type(cwd: str) -> str:
    """Detect project type based on config files."""
    indicators = {
        "package.json": "Node.js", "Cargo.toml": "Rust", "pyproject.toml": "Python",
        "setup.py": "Python", "go.mod": "Go", "pom.xml": "Java/Maven",
        "build.gradle": "Java/Gradle", "CMakeLists.txt": "C/C++ (CMake)",
        "Makefile": "Make", "Gemfile": "Ruby", "composer.json": "PHP",
        "mix.exs": "Elixir", "pubspec.yaml": "Dart/Flutter",
    }
    cwd_path = Path(cwd)
    detected = [lang for file, lang in indicators.items() if (cwd_path / file).exists()]
    return f"Type: {', '.join(detected[:3])}" if detected else ""


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
            lines = f.readlines()[-100:]
            for line in lines:
                try:
                    entry = json.loads(line)
                    if entry.get("level") == "error":
                        errors.append(f"{entry.get('hook')}: {entry.get('data', {}).get('msg', 'unknown')}")
                except json.JSONDecodeError:
                    continue

        if errors:
            recent = errors[-3:]
            return f"Recent hook errors: {', '.join(recent)}"
    except Exception:
        pass

    return ""


def get_codebase_map(cwd: str, max_depth: int = 3) -> str:
    """Generate concise project structure map."""
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

        entries = [e for e in entries if not should_ignore(e.name) and not e.name.startswith('.')]

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

        project_name = cwd_path.name
        return f"Project: {project_name}/\n" + "\n".join(tree_lines)
    except Exception:
        return ""


def get_usage_summary() -> str:
    """Get compact usage stats for today."""
    parts = []
    today = datetime.now().strftime("%Y-%m-%d")

    # Count sessions in last 24h
    projects_dir = Path.home() / ".claude" / "projects"
    if projects_dir.exists():
        try:
            yesterday = datetime.now() - timedelta(days=1)
            session_count = sum(1 for jsonl in projects_dir.rglob("*.jsonl")
                              if datetime.fromtimestamp(jsonl.stat().st_mtime) > yesterday)
            if session_count > 0:
                parts.append(f"Sessions (24h): {session_count}")
        except Exception:
            pass

    # Get agent/skill usage
    usage_file = Path.home() / ".claude" / "data" / "usage-stats.json"
    if usage_file.exists():
        try:
            with open(usage_file) as f:
                usage = json.load(f)
            daily = usage.get("daily", {}).get(today, {})
            usage_parts = []
            if cnt := daily.get("agents"):
                usage_parts.append(f"{cnt} agents")
            if cnt := daily.get("skills"):
                usage_parts.append(f"{cnt} skills")
            if usage_parts:
                parts.append(f"Today: {', '.join(usage_parts)}")

            # Top agent
            agents = usage.get("agents", {})
            if agents:
                top = max(agents.items(), key=lambda x: x[1].get("count", 0))
                if top[1].get("count", 0) > 2:
                    parts.append(f"Top agent: {top[0]} ({top[1]['count']}x)")
        except Exception:
            pass

    return ", ".join(parts) if parts else ""


def handle_session_context(cwd: str) -> list:
    """Main session context handler."""
    output_parts = []

    git_ctx = get_git_context(cwd)
    if git_ctx:
        output_parts.extend(git_ctx)

    if usage := get_usage_summary():
        output_parts.append(usage)

    if project_type := detect_project_type(cwd):
        output_parts.append(project_type)

    return output_parts


# =============================================================================
# Start Viewer Handler
# =============================================================================

VIEWER_CMD = "claude-code-viewer"
DATA_DIR = Path.home() / ".claude" / "data"
PID_FILE = DATA_DIR / ".viewer.pid"
DEFAULT_PORT = 3000


def is_viewer_running() -> bool:
    """Check if viewer process is running."""
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
            os.kill(pid, 0)
            return True
        except (ValueError, ProcessLookupError, PermissionError):
            PID_FILE.unlink(missing_ok=True)

    # Fallback: pgrep
    try:
        result = subprocess.run(["pgrep", "-f", VIEWER_CMD], capture_output=True, text=True, timeout=2)
        return bool(result.stdout.strip())
    except Exception:
        pass
    return False


def start_viewer() -> str | None:
    """Start the viewer in background, return message if started."""
    try:
        process = subprocess.Popen(
            [VIEWER_CMD],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )
        PID_FILE.parent.mkdir(parents=True, exist_ok=True)
        PID_FILE.write_text(str(process.pid))
        return f"Started claude-code-viewer on http://localhost:{DEFAULT_PORT}"
    except FileNotFoundError:
        return None
    except Exception:
        return None


def handle_start_viewer() -> str | None:
    """Start viewer handler - only runs once per session."""
    session_marker = DATA_DIR / ".viewer_checked"
    import time
    now = time.time()

    if session_marker.exists():
        try:
            last_check = float(session_marker.read_text().strip())
            if now - last_check < 60:
                return None
        except (ValueError, OSError):
            pass

    session_marker.write_text(str(now))

    if is_viewer_running():
        return None

    return start_viewer()


# =============================================================================
# Dispatcher
# =============================================================================

class SessionStartDispatcher(SimpleDispatcher):
    """SessionStart event dispatcher."""

    DISPATCHER_NAME = "session_start_dispatcher"
    EVENT_TYPE = None  # SessionStart doesn't have event_type in context

    def handle(self, ctx: dict) -> list[str]:
        cwd = ctx.get('cwd', os.getcwd())
        output_parts = ["[Session Start]"]

        # Handler 1: Session context (git, usage, project type)
        context = handle_session_context(cwd)
        output_parts.extend(context)

        # Handler 2: Start viewer (optional)
        if viewer_msg := handle_start_viewer():
            output_parts.append(viewer_msg)

        # Only return if there's content beyond the header
        return output_parts if len(output_parts) > 1 else []


if __name__ == "__main__":
    SessionStartDispatcher().run()

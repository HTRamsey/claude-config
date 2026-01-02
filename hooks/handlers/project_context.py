"""
Project context handler - project detection and usage statistics.

Provides project type detection, codebase mapping, and usage summaries
for session_start dispatcher.
"""
import json
from datetime import datetime, timedelta
from pathlib import Path


# Project type indicators
PROJECT_INDICATORS = {
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

# Directories to ignore in codebase map
IGNORE_DIRS = frozenset({
    'node_modules', 'vendor', 'build', 'dist', '__pycache__',
    '.git', '.svn', '.hg', 'target', 'out', 'bin', 'obj',
    'venv', '.venv', 'env', '.env', 'coverage', '.cache',
    '.tox', '.pytest_cache', '.mypy_cache', 'htmlcov',
})

IGNORE_PATTERNS = frozenset({'.min.js', '.min.css', '.map', '.lock'})


def detect_project_type(cwd: str) -> str:
    """Detect project type based on config files.

    Returns:
        Formatted string like "Type: Python, Node.js" or empty string.
    """
    cwd_path = Path(cwd)
    detected = [lang for file, lang in PROJECT_INDICATORS.items() if (cwd_path / file).exists()]
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

    def should_ignore(name: str) -> bool:
        if name in IGNORE_DIRS:
            return True
        return any(name.endswith(pattern) for pattern in IGNORE_PATTERNS)

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

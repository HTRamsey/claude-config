"""
Transcript utilities - Unified transcript parsing and analysis.

Consolidates transcript parsing logic from:
- transcript_converter.py: Full conversion
- session_persistence.py: Project info extraction
- auto_continue.py: Last messages extraction

Usage:
    from hooks.hook_utils.transcript import (
        iter_transcript,
        extract_messages,
        analyze_tool_usage,
        get_last_assistant_content,
    )
"""
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterator

from hooks.hook_utils.io import iter_jsonl


# Technology detection patterns
TECH_PATTERNS = {
    r"\.py$": "Python",
    r"\.ts$|\.tsx$": "TypeScript",
    r"\.js$|\.jsx$": "JavaScript",
    r"\.rs$": "Rust",
    r"\.go$": "Go",
    r"\.java$": "Java",
    r"\.cpp$|\.cc$|\.h$": "C++",
    r"requirements\.txt|pyproject\.toml": "Python",
    r"package\.json": "Node.js",
    r"Cargo\.toml": "Rust",
    r"go\.mod": "Go",
    r"CMakeLists\.txt": "CMake",
    r"Makefile": "Make",
    r"Dockerfile": "Docker",
    r"\.github/workflows": "GitHub Actions",
}


def iter_transcript(
    path: str | Path,
    tail: int | None = None
) -> Iterator[dict]:
    """Iterate over transcript entries.

    Wrapper around iter_jsonl with transcript-specific defaults.

    Args:
        path: Path to transcript.jsonl file
        tail: If set, only yield last N entries

    Yields:
        Parsed transcript entry dicts
    """
    yield from iter_jsonl(path, tail=tail, skip_errors=True)


def extract_messages(
    path: str | Path,
    role: str | None = None,
    tail: int | None = None
) -> list[dict]:
    """Extract messages from transcript, optionally filtering by role.

    Args:
        path: Path to transcript file
        role: Filter by role ("user", "assistant", "tool"). None = all.
        tail: Only process last N entries from transcript

    Returns:
        List of message dicts with normalized structure:
        {
            "role": "user" | "assistant" | "tool",
            "content": str,
            "timestamp": str | None,
            "tool_calls": list | None  # For assistant messages with tool use
        }
    """
    messages = []

    for entry in iter_transcript(path, tail=tail):
        msg_type = entry.get("type")

        if msg_type == "user" or msg_type == "human":
            if role and role not in ("user", "human"):
                continue
            messages.append({
                "role": "user",
                "content": entry.get("content", ""),
                "timestamp": entry.get("timestamp"),
            })

        elif msg_type == "assistant":
            if role and role != "assistant":
                continue
            content = entry.get("content", "")
            tool_calls = []

            if "tool_use" in entry:
                for tool in entry.get("tool_use", []):
                    tool_calls.append({
                        "name": tool.get("name"),
                        "input": tool.get("input"),
                    })

            msg = {
                "role": "assistant",
                "content": content,
                "timestamp": entry.get("timestamp"),
            }
            if tool_calls:
                msg["tool_calls"] = tool_calls
            messages.append(msg)

        elif msg_type == "tool_result":
            if role and role != "tool":
                continue
            result = entry.get("result", "")
            messages.append({
                "role": "tool",
                "tool_name": entry.get("tool_name"),
                "result": result[:500] if isinstance(result, str) else result,
                "timestamp": entry.get("timestamp"),
            })

    return messages


def get_last_assistant_content(path: str | Path, tail: int = 50) -> str | None:
    """Get content of last assistant message.

    Args:
        path: Path to transcript file
        tail: Number of entries to scan from end

    Returns:
        Content string or None if no assistant message found
    """
    messages = extract_messages(path, role="assistant", tail=tail)
    if not messages:
        return None

    content = messages[-1].get("content", "")
    if isinstance(content, list):
        # Handle structured content
        content = " ".join(
            str(c.get("text", "")) for c in content if isinstance(c, dict)
        )
    return content.lower() if content else None


def analyze_tool_usage(path: str | Path) -> dict[str, Any]:
    """Analyze tool usage patterns from transcript.

    Args:
        path: Path to transcript file

    Returns:
        Dict with keys:
        - tools_used: Dict[str, int] - tool name to count
        - files_modified: list[str] - files edited
        - files_created: list[str] - files written
        - technologies: list[str] - detected technologies
        - error_count: int - number of error entries
    """
    tools_used: dict[str, int] = defaultdict(int)
    files_modified: set[str] = set()
    files_created: set[str] = set()
    technologies: set[str] = set()
    error_count = 0

    for entry in iter_transcript(path):
        tool = entry.get("tool_name", "")
        if tool:
            tools_used[tool] += 1

        tool_input = entry.get("tool_input", {})
        file_path = tool_input.get("file_path", "")

        if tool == "Edit" and file_path:
            files_modified.add(file_path)
        elif tool == "Write" and file_path:
            files_created.add(file_path)

        if file_path:
            for pattern, tech in TECH_PATTERNS.items():
                if re.search(pattern, file_path):
                    technologies.add(tech)

        content = str(entry.get("content", ""))
        if "error" in content.lower() and len(content) < 200:
            error_count += 1

    return {
        "tools_used": dict(tools_used),
        "files_modified": list(files_modified),
        "files_created": list(files_created),
        "technologies": list(technologies),
        "error_count": error_count,
    }


def detect_project_root(path: str | Path) -> str | None:
    """Detect project root from file paths in transcript.

    Args:
        path: Path to transcript file

    Returns:
        Project root path or None if not detected
    """
    project_markers = [
        "package.json", "pyproject.toml", "Cargo.toml",
        "go.mod", ".git", "Makefile", "CMakeLists.txt",
        "settings.json", "CLAUDE.md"
    ]

    for entry in iter_transcript(path):
        tool_input = entry.get("tool_input", {})
        file_path = tool_input.get("file_path", "")
        if not file_path:
            continue

        file_path = Path(file_path)
        for parent in file_path.parents:
            if any((parent / marker).exists() for marker in project_markers):
                return str(parent)

    return None


def count_tool_calls(path: str | Path, tool_name: str | None = None) -> int:
    """Count tool calls in transcript.

    Args:
        path: Path to transcript file
        tool_name: If set, count only this tool. None = count all.

    Returns:
        Number of tool calls
    """
    count = 0
    for entry in iter_transcript(path):
        tool = entry.get("tool_name", "")
        if tool and (tool_name is None or tool == tool_name):
            count += 1
    return count

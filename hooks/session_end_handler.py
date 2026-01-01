#!/home/jonglaser/.claude/data/venv/bin/python3
"""
Session End Handler - Unified handler for SessionEnd events.

Consolidates:
- session_persistence: Auto-save session insights to memory MCP
- transcript_converter: Convert JSONL transcripts to readable JSON

Runs on SessionEnd event to capture learnings before conversation ends.
"""
import json
import os
import re
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from hook_utils import graceful_main, log_event, get_session_id


# =============================================================================
# Session Persistence (from session_persistence.py)
# =============================================================================

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


def extract_project_info(transcript_path: str) -> dict:
    """Extract project-related information from transcript."""
    info = {
        "project_root": None,
        "files_modified": set(),
        "files_created": set(),
        "patterns_discovered": [],
        "errors_encountered": [],
        "tools_used": defaultdict(int),
        "technologies": set(),
    }

    if not transcript_path or not os.path.exists(transcript_path):
        return info

    try:
        with open(transcript_path, 'r') as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())

                    tool = entry.get("tool_name", "")
                    if tool:
                        info["tools_used"][tool] += 1

                    tool_input = entry.get("tool_input", {})
                    file_path = tool_input.get("file_path", "")

                    if tool == "Edit" and file_path:
                        info["files_modified"].add(file_path)
                    elif tool == "Write" and file_path:
                        info["files_created"].add(file_path)

                    if file_path:
                        for pattern, tech in TECH_PATTERNS.items():
                            if re.search(pattern, file_path):
                                info["technologies"].add(tech)

                    if file_path and not info["project_root"]:
                        path = Path(file_path)
                        for parent in path.parents:
                            if any((parent / f).exists() for f in [
                                "package.json", "pyproject.toml", "Cargo.toml",
                                "go.mod", ".git", "Makefile", "CMakeLists.txt",
                                "settings.json", "CLAUDE.md"
                            ]):
                                info["project_root"] = str(parent)
                                break

                    content = str(entry.get("content", ""))
                    if "error" in content.lower() and len(content) < 200:
                        info["errors_encountered"].append(content[:100])

                except json.JSONDecodeError:
                    continue

    except Exception:
        pass

    info["files_modified"] = list(info["files_modified"])
    info["files_created"] = list(info["files_created"])
    info["technologies"] = list(info["technologies"])
    info["tools_used"] = dict(info["tools_used"])

    return info


def cleanup_old_session_files(max_age_hours: int = 24) -> int:
    """Clean up old file-history snapshots."""
    now = time.time()
    cleaned = 0

    file_history = Path.home() / ".claude" / "data" / "file-history"
    if file_history.exists():
        max_history_age = 30 * 24 * 3600  # 30 days
        for file in file_history.rglob("*"):
            if file.is_file():
                try:
                    if now - file.stat().st_mtime > max_history_age:
                        file.unlink()
                        cleaned += 1
                except (OSError, IOError):
                    continue

    return cleaned


def generate_memory_suggestions(info: dict) -> dict:
    """Generate memory MCP suggestions based on extracted info."""
    suggestions = {"entities": [], "observations": []}

    project_root = info.get("project_root")
    if not project_root:
        return suggestions

    project_name = Path(project_root).name
    observations = []

    if info["technologies"]:
        observations.append(f"Technologies: {', '.join(info['technologies'])}")

    if info["files_modified"]:
        dirs = set(str(Path(f).parent) for f in info["files_modified"])
        observations.append(f"Active directories: {', '.join(list(dirs)[:5])}")

    if info["files_created"]:
        observations.append(f"Files created this session: {', '.join(Path(f).name for f in list(info['files_created'])[:5])}")

    top_tools = sorted(info["tools_used"].items(), key=lambda x: -x[1])[:3]
    if top_tools:
        tool_summary = ", ".join(f"{t}:{c}" for t, c in top_tools)
        observations.append(f"Common operations: {tool_summary}")

    if observations:
        suggestions["entities"].append({
            "name": project_name,
            "entityType": "project",
            "observations": observations
        })
        suggestions["observations"].append({
            "entityName": project_name,
            "contents": observations
        })

    return suggestions


def save_session_metadata(session_id: str, info: dict, transcript_path: str):
    """Save session metadata for better resumption."""
    if not session_id:
        return

    session_file = Path.home() / ".claude" / "data" / "session-history.json"
    history = {}

    try:
        if session_file.exists():
            with open(session_file) as f:
                history = json.load(f)
    except (json.JSONDecodeError, IOError):
        history = {}

    history[session_id] = {
        "project_root": info.get("project_root"),
        "technologies": info.get("technologies", []),
        "files_modified_count": len(info.get("files_modified", [])),
        "last_accessed": datetime.now().isoformat(),
        "transcript_path": transcript_path
    }

    if len(history) > 50:
        sorted_sessions = sorted(
            history.items(),
            key=lambda x: x[1].get("last_accessed", ""),
            reverse=True
        )
        history = dict(sorted_sessions[:50])

    try:
        session_file.parent.mkdir(parents=True, exist_ok=True)
        with open(session_file, "w") as f:
            json.dump(history, f, indent=2)
    except IOError:
        pass


# =============================================================================
# Transcript Converter (from transcript_converter.py)
# =============================================================================

def find_transcript_files() -> list[Path]:
    """Find Claude Code transcript files."""
    paths_to_check = [
        Path.home() / ".claude" / "projects",
        Path.home() / ".claude-code",
        Path("/tmp") / "claude-code",
    ]

    transcript_files = []
    for base_path in paths_to_check:
        if base_path.exists():
            for transcript in base_path.rglob("transcript.jsonl"):
                transcript_files.append(transcript)

    return transcript_files


def parse_jsonl(file_path: Path) -> list[dict[str, Any]]:
    """Parse JSONL file into list of dicts."""
    entries = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                log_event("session_end_handler", "parse_error", {"file": str(file_path), "line": line_num})
    return entries


def extract_messages(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Extract user/assistant messages from transcript entries."""
    messages = []

    for entry in entries:
        msg_type = entry.get("type")

        if msg_type == "user":
            messages.append({
                "role": "user",
                "content": entry.get("content", ""),
                "timestamp": entry.get("timestamp"),
            })
        elif msg_type == "assistant":
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
            messages.append({
                "role": "tool",
                "tool_name": entry.get("tool_name"),
                "result": (
                    entry.get("result", "")[:500]
                    if isinstance(entry.get("result"), str)
                    else entry.get("result")
                ),
                "timestamp": entry.get("timestamp"),
            })

    return messages


def convert_transcript(transcript_path: Path, output_dir: Path, mode: str) -> Path:
    """Convert a single transcript file."""
    entries = parse_jsonl(transcript_path)
    messages = extract_messages(entries)

    session_id = transcript_path.parent.name
    if not session_id or session_id == "projects":
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    output_file = output_dir / f"{session_id}.json"

    existing_messages = []
    if mode == "append" and output_file.exists():
        with open(output_file, "r", encoding="utf-8") as f:
            existing = json.load(f)
            existing_messages = existing.get("messages", [])

    existing_timestamps = {m.get("timestamp") for m in existing_messages}
    new_messages = [m for m in messages if m.get("timestamp") not in existing_timestamps]
    all_messages = existing_messages + new_messages

    output = {
        "session_id": session_id,
        "converted_at": datetime.now().isoformat(),
        "source": str(transcript_path),
        "message_count": len(all_messages),
        "messages": all_messages,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, default=str)

    return output_file


def run_transcript_converter() -> list[str]:
    """Run transcript conversion if enabled. Returns list of converted files."""
    if os.environ.get("CLAUDE_TRANSCRIPT_CONVERT", "false").lower() != "true":
        return []

    mode = os.environ.get("CLAUDE_TRANSCRIPT_MODE", "append")
    output_dir = Path.home() / ".claude" / "data" / "transcripts"

    transcript_files = find_transcript_files()
    converted = []

    for transcript in transcript_files:
        try:
            output = convert_transcript(transcript, output_dir, mode)
            converted.append(str(output))
            log_event("session_end_handler", "converted", {"source": str(transcript), "output": str(output)})
        except Exception as e:
            log_event("session_end_handler", "error", {"file": str(transcript), "error": str(e)}, level="error")

    return converted


# =============================================================================
# Combined Handler
# =============================================================================

def handle_session_end(ctx: dict) -> list[str]:
    """
    Handle SessionEnd event.

    Returns list of output messages.
    """
    messages = []

    # Clean up old session files
    cleaned = cleanup_old_session_files(max_age_hours=24)
    if cleaned > 0:
        messages.append(f"[Session Cleanup] Removed {cleaned} old session files")

    transcript_path = ctx.get("transcript_path", "")
    session_id = get_session_id(ctx)

    # Extract information from transcript
    info = extract_project_info(transcript_path)

    # Save session metadata for better resumption
    save_session_metadata(session_id, info, transcript_path)

    # Skip if minimal activity
    total_tool_uses = sum(info["tools_used"].values())
    if total_tool_uses >= 5:
        # Generate memory suggestions
        suggestions = generate_memory_suggestions(info)

        if suggestions["entities"] or suggestions["observations"]:
            messages.append("[Session Persistence] Suggested memory updates:")
            messages.append("")

            if suggestions["entities"]:
                entity = suggestions["entities"][0]
                messages.append(f"  Project: {entity['name']}")
                messages.append("  Observations to save:")
                for obs in entity["observations"]:
                    messages.append(f"    - {obs}")

            messages.append("")
            messages.append("  To persist, use memory MCP:")
            messages.append("    mcp__memory__add_observations or mcp__memory__create_entities")

    # Run transcript converter if enabled
    converted = run_transcript_converter()
    if converted:
        messages.append(f"[Transcript Converter] Converted {len(converted)} transcript(s)")

    return messages


# =============================================================================
# Main
# =============================================================================

@graceful_main("session_end_handler")
def main():
    try:
        ctx = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    messages = handle_session_end(ctx)
    for msg in messages:
        print(msg)

    sys.exit(0)


if __name__ == "__main__":
    main()

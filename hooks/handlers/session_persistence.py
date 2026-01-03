"""
Session persistence handler - transcript parsing and memory suggestions.

Provides project info extraction, memory MCP suggestions, and session metadata
for session_end dispatcher.
"""
import heapq
import json
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from hooks.hook_utils import get_session_id, log_event
from hooks.hook_utils.transcript import analyze_tool_usage, detect_project_root
from hooks.handlers import transcript_converter


def extract_project_info(transcript_path: str) -> dict[str, Any]:
    """Extract project-related information from transcript.

    Returns:
        Dict with keys: project_root, files_modified, files_created,
        patterns_discovered, errors_encountered, tools_used, technologies
    """
    if not transcript_path:
        return {
            "project_root": None,
            "files_modified": [],
            "files_created": [],
            "patterns_discovered": [],
            "errors_encountered": [],
            "tools_used": {},
            "technologies": [],
        }

    # Use transcript utilities for analysis
    analysis = analyze_tool_usage(transcript_path)
    project_root = detect_project_root(transcript_path)

    return {
        "project_root": project_root,
        "files_modified": analysis.get("files_modified", []),
        "files_created": analysis.get("files_created", []),
        "patterns_discovered": [],
        "errors_encountered": [],
        "tools_used": analysis.get("tools_used", {}),
        "technologies": analysis.get("technologies", []),
    }


def cleanup_old_session_files(max_age_hours: int = 24) -> int:
    """Clean up old file-history snapshots.

    Args:
        max_age_hours: Maximum age in hours before files are cleaned up.
                       Note: file-history uses 30 days regardless of this param
                       as those files are needed for longer-term analysis.

    Returns:
        Number of files cleaned up.
    """
    now = time.time()
    cleaned = 0
    max_age_seconds = max_age_hours * 3600

    file_history = Path.home() / ".claude" / "data" / "file-history"
    if file_history.exists():
        # File history kept for 30 days for analysis, regardless of max_age_hours
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


def generate_memory_suggestions(info: dict) -> dict[str, list]:
    """Generate memory MCP suggestions based on extracted info.

    Returns:
        Dict with 'entities' and 'observations' lists for memory MCP.
    """
    suggestions = {"entities": [], "observations": []}

    project_root = info.get("project_root")
    if not project_root:
        return suggestions

    project_name = Path(project_root).name
    observations = []

    if info.get("technologies"):
        observations.append(f"Technologies: {', '.join(info['technologies'])}")

    if info.get("files_modified"):
        dirs = set(str(Path(f).parent) for f in info["files_modified"])
        observations.append(f"Active directories: {', '.join(list(dirs)[:5])}")

    if info.get("files_created"):
        observations.append(
            f"Files created this session: {', '.join(Path(f).name for f in list(info['files_created'])[:5])}"
        )

    top_tools = heapq.nlargest(3, info.get("tools_used", {}).items(), key=lambda x: x[1])
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


def save_session_metadata(session_id: str, info: dict, transcript_path: str) -> None:
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

    # Keep only last 50 sessions
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


def format_memory_suggestions(suggestions: dict) -> list[str]:
    """Format memory suggestions for display.

    Returns:
        List of formatted message strings.
    """
    messages = []

    if not suggestions.get("entities"):
        return messages

    messages.append("[Session Persistence] Suggested memory updates:")
    messages.append("")

    entity = suggestions["entities"][0]
    messages.append(f"  Project: {entity['name']}")
    messages.append("  Observations to save:")
    for obs in entity["observations"]:
        messages.append(f"    - {obs}")

    messages.append("")
    messages.append("  To persist, use memory MCP:")
    messages.append("    mcp__memory__add_observations or mcp__memory__create_entities")

    return messages


def update_usage_cache() -> None:
    """Update usage cache for statusline."""
    usage_script = Path.home() / ".claude/scripts/diagnostics/usage-stats.py"
    if usage_script.exists():
        try:
            subprocess.run(
                [str(usage_script), "--update-cache"],
                capture_output=True,
                timeout=10
            )
        except subprocess.TimeoutExpired:
            log_event("session_persistence", "usage_cache_timeout", {
                "script": str(usage_script)
            }, "warning")
        except OSError as e:
            log_event("session_persistence", "usage_cache_error", {
                "script": str(usage_script),
                "error": str(e)
            }, "warning")


def handle_session_end(ctx: dict) -> list[str]:
    """Unified SessionEnd handler - handles all session end tasks.

    Args:
        ctx: Context with 'transcript_path' key

    Returns:
        List of output message lines
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

    # Skip memory suggestions if minimal activity
    total_tool_uses = sum(info.get("tools_used", {}).values())
    if total_tool_uses >= 5:
        suggestions = generate_memory_suggestions(info)
        if suggestions.get("entities"):
            messages.extend(format_memory_suggestions(suggestions))

    # Run transcript converter if enabled
    converted = transcript_converter.run_converter()
    if converted:
        messages.append(f"[Transcript Converter] Converted {len(converted)} transcript(s)")

    # Update usage cache for statusline
    update_usage_cache()

    return messages

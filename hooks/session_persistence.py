#!/home/jonglaser/.claude/data/venv/bin/python3
"""
Session Persistence Hook - Auto-saves session insights to memory MCP on Stop.
Analyzes the transcript to extract valuable information worth persisting.

Runs on Stop event to capture learnings before conversation ends.
"""
import json
import os
import sys
import re
from pathlib import Path
from collections import defaultdict
from datetime import datetime

# Import shared utilities
sys.path.insert(0, str(Path(__file__).parent))
from hook_utils import graceful_main, log_event, get_session_id

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

    # Technology indicators
    tech_patterns = {
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

    try:
        with open(transcript_path, 'r') as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())

                    # Track tools used
                    tool = entry.get("tool_name", "")
                    if tool:
                        info["tools_used"][tool] += 1

                    tool_input = entry.get("tool_input", {})
                    file_path = tool_input.get("file_path", "")

                    # Track file modifications
                    if tool == "Edit" and file_path:
                        info["files_modified"].add(file_path)
                    elif tool == "Write" and file_path:
                        info["files_created"].add(file_path)

                    # Detect technologies from file paths
                    if file_path:
                        for pattern, tech in tech_patterns.items():
                            if re.search(pattern, file_path):
                                info["technologies"].add(tech)

                    # Extract project root from paths
                    if file_path and not info["project_root"]:
                        # Heuristic: find common project indicators
                        path = Path(file_path)
                        for parent in path.parents:
                            if any((parent / f).exists() for f in [
                                "package.json", "pyproject.toml", "Cargo.toml",
                                "go.mod", ".git", "Makefile", "CMakeLists.txt",
                                "settings.json", "CLAUDE.md"  # Claude config dirs
                            ]):
                                info["project_root"] = str(parent)
                                break
                        # Fallback: use deepest common directory of modified files
                        if not info["project_root"] and len(info["files_modified"]) > 0:
                            all_paths = list(info["files_modified"]) + list(info["files_created"])
                            if all_paths:
                                common = os.path.commonpath(all_paths)
                                if common and common != "/":
                                    info["project_root"] = common

                    # Track errors
                    content = str(entry.get("content", ""))
                    if "error" in content.lower() and len(content) < 200:
                        info["errors_encountered"].append(content[:100])

                except json.JSONDecodeError:
                    continue

    except Exception:
        pass

    # Convert sets to lists for JSON serialization
    info["files_modified"] = list(info["files_modified"])
    info["files_created"] = list(info["files_created"])
    info["technologies"] = list(info["technologies"])
    info["tools_used"] = dict(info["tools_used"])

    return info

def cleanup_old_session_files(max_age_hours: int = 24):
    """Clean up old file-history snapshots."""
    import time

    now = time.time()
    cleaned = 0

    # Clean old file-history snapshots (30 days)
    file_history = Path.home() / ".claude" / "file-history"
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
    suggestions = {
        "entities": [],
        "observations": [],
    }

    project_root = info.get("project_root")
    if not project_root:
        return suggestions

    project_name = Path(project_root).name

    # Build observations for the project
    observations = []

    # Technologies
    if info["technologies"]:
        observations.append(f"Technologies: {', '.join(info['technologies'])}")

    # File activity summary
    if info["files_modified"]:
        # Group by directory
        dirs = set(str(Path(f).parent) for f in info["files_modified"])
        observations.append(f"Active directories: {', '.join(list(dirs)[:5])}")

    if info["files_created"]:
        observations.append(f"Files created this session: {', '.join(Path(f).name for f in list(info['files_created'])[:5])}")

    # Tool usage pattern
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

        # Also suggest adding to existing entity if it exists
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

    # Store session info (keep last 50 sessions)
    history[session_id] = {
        "project_root": info.get("project_root"),
        "technologies": info.get("technologies", []),
        "files_modified_count": len(info.get("files_modified", [])),
        "last_accessed": datetime.now().isoformat(),
        "transcript_path": transcript_path
    }

    # Prune to 50 most recent
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


@graceful_main("session_persistence")
def main():
    try:
        ctx = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    # Clean up old session files on every session end
    cleaned = cleanup_old_session_files(max_age_hours=24)
    if cleaned > 0:
        print(f"[Session Cleanup] Removed {cleaned} old session files")

    transcript_path = ctx.get("transcript_path", "")
    stop_reason = ctx.get("stop_hook_reason", "unknown")
    session_id = get_session_id(ctx)

    # Extract information from transcript
    info = extract_project_info(transcript_path)

    # Save session metadata for better resumption
    save_session_metadata(session_id, info, transcript_path)

    # Skip if minimal activity
    total_tool_uses = sum(info["tools_used"].values())
    if total_tool_uses < 5:
        sys.exit(0)

    # Generate memory suggestions
    suggestions = generate_memory_suggestions(info)

    if suggestions["entities"] or suggestions["observations"]:
        print("[Session Persistence] Suggested memory updates:")
        print()

        if suggestions["entities"]:
            entity = suggestions["entities"][0]
            print(f"  Project: {entity['name']}")
            print("  Observations to save:")
            for obs in entity["observations"]:
                print(f"    - {obs}")

        print()
        print("  To persist, use memory MCP:")
        print("    mcp__memory__add_observations or mcp__memory__create_entities")

        # Also output as JSON for potential automation
        print()
        print("  JSON format:")
        print(f"    {json.dumps(suggestions, indent=2)[:500]}...")

    sys.exit(0)

if __name__ == "__main__":
    main()

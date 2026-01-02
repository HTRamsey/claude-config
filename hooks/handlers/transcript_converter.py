"""
Transcript converter handler - JSONL to JSON transcript conversion.

Provides transcript file discovery, parsing, and conversion
for session_end dispatcher.
"""
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from hooks.hook_utils import log_event
from hooks.hook_utils.io import iter_jsonl


def find_transcript_files() -> list[Path]:
    """Find Claude Code transcript files.

    Returns:
        List of transcript.jsonl file paths.
    """
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
    """Parse JSONL file into list of dicts.

    Uses iter_jsonl utility with skip_errors=True (logs errors internally).

    Returns:
        List of parsed JSON objects.
    """
    return list(iter_jsonl(file_path, skip_errors=True))


def extract_messages(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Extract user/assistant messages from transcript entries.

    Returns:
        List of normalized message dicts with role, content, timestamp.
    """
    messages = []

    for entry in entries:
        msg_type = entry.get("type")

        match msg_type:
            case "user":
                messages.append({
                    "role": "user",
                    "content": entry.get("content", ""),
                    "timestamp": entry.get("timestamp"),
                })
            case "assistant":
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
            case "tool_result":
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


def convert_transcript(transcript_path: Path, output_dir: Path, mode: str = "append") -> Path:
    """Convert a single transcript file to JSON.

    Args:
        transcript_path: Path to source transcript.jsonl
        output_dir: Directory to write output JSON
        mode: "append" to merge with existing, "overwrite" to replace

    Returns:
        Path to the output JSON file.
    """
    entries = parse_jsonl(transcript_path)
    messages = extract_messages(entries)

    session_id = transcript_path.parent.name
    if not session_id or session_id == "projects":
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    output_file = output_dir / f"{session_id}.json"

    existing_messages = []
    if mode == "append" and output_file.exists():
        try:
            with open(output_file, "r", encoding="utf-8") as f:
                existing = json.load(f)
                existing_messages = existing.get("messages", [])
        except (json.JSONDecodeError, ValueError) as e:
            log_event("transcript_converter", "corrupt_json", {
                "file": str(output_file),
                "error": str(e)
            }, "warning")
            # Fall back to overwrite mode on corruption

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


def run_converter() -> list[str]:
    """Run transcript conversion if enabled.

    Checks CLAUDE_TRANSCRIPT_CONVERT environment variable.

    Returns:
        List of converted file paths (as strings).
    """
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
            log_event("transcript_converter", "converted", {
                "source": str(transcript),
                "output": str(output)
            })
        except Exception as e:
            log_event("transcript_converter", "error", {
                "file": str(transcript),
                "error": str(e)
            }, level="error")

    return converted

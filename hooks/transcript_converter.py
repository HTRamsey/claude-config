#!/usr/bin/env python3
"""
Transcript Converter Hook - converts JSONL transcripts to readable JSON.

Event: SessionEnd
Converts Claude Code's JSONL transcripts to human-readable JSON format.

Environment variables:
  CLAUDE_TRANSCRIPT_CONVERT=true   Enable conversion (default: false)
  CLAUDE_TRANSCRIPT_MODE=append    Options: append, overwrite (default: append)

Output: ~/.claude/data/transcripts/<session_id>.json
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from hook_utils import graceful_main, log_event


def find_transcript_files() -> list[Path]:
    """Find Claude Code transcript files."""
    # Check common locations
    paths_to_check = [
        Path.home() / ".claude" / "projects",
        Path.home() / ".claude-code",
        Path("/tmp") / "claude-code",
    ]

    transcript_files = []
    for base_path in paths_to_check:
        if base_path.exists():
            # Find all transcript.jsonl files
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
                log_event(
                    "transcript_converter",
                    "parse_error",
                    {"file": str(file_path), "line": line_num},
                )
    return entries


def extract_messages(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Extract user/assistant messages from transcript entries."""
    messages = []

    for entry in entries:
        msg_type = entry.get("type")

        if msg_type == "user":
            messages.append(
                {
                    "role": "user",
                    "content": entry.get("content", ""),
                    "timestamp": entry.get("timestamp"),
                }
            )

        elif msg_type == "assistant":
            content = entry.get("content", "")
            tool_calls = []

            # Extract tool calls if present
            if "tool_use" in entry:
                for tool in entry.get("tool_use", []):
                    tool_calls.append(
                        {
                            "name": tool.get("name"),
                            "input": tool.get("input"),
                        }
                    )

            msg = {
                "role": "assistant",
                "content": content,
                "timestamp": entry.get("timestamp"),
            }
            if tool_calls:
                msg["tool_calls"] = tool_calls

            messages.append(msg)

        elif msg_type == "tool_result":
            messages.append(
                {
                    "role": "tool",
                    "tool_name": entry.get("tool_name"),
                    "result": (
                        entry.get("result", "")[:500]
                        if isinstance(entry.get("result"), str)
                        else entry.get("result")
                    ),  # Truncate long results
                    "timestamp": entry.get("timestamp"),
                }
            )

    return messages


def convert_transcript(transcript_path: Path, output_dir: Path, mode: str) -> Path:
    """Convert a single transcript file."""
    entries = parse_jsonl(transcript_path)
    messages = extract_messages(entries)

    # Generate session ID from path or timestamp
    session_id = transcript_path.parent.name
    if not session_id or session_id == "projects":
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    output_file = output_dir / f"{session_id}.json"

    # Handle append mode
    existing_messages = []
    if mode == "append" and output_file.exists():
        with open(output_file, "r", encoding="utf-8") as f:
            existing = json.load(f)
            existing_messages = existing.get("messages", [])

    # Deduplicate based on timestamp
    existing_timestamps = {m.get("timestamp") for m in existing_messages}
    new_messages = [m for m in messages if m.get("timestamp") not in existing_timestamps]

    # Combine
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


def run_hook(context: dict[str, Any]) -> dict[str, Any]:
    """Main hook entry point."""
    # Check if conversion is enabled
    if os.environ.get("CLAUDE_TRANSCRIPT_CONVERT", "false").lower() != "true":
        return {"result": "continue"}

    mode = os.environ.get("CLAUDE_TRANSCRIPT_MODE", "append")
    output_dir = Path.home() / ".claude" / "data" / "transcripts"

    # Find and convert transcripts
    transcript_files = find_transcript_files()
    converted = []

    for transcript in transcript_files:
        try:
            output = convert_transcript(transcript, output_dir, mode)
            converted.append(str(output))
            log_event(
                "transcript_converter",
                "converted",
                {"source": str(transcript), "output": str(output)},
            )
        except Exception as e:
            log_event(
                "transcript_converter",
                "error",
                {"file": str(transcript), "error": str(e)},
                level="error",
            )

    return {
        "result": "continue",
        "message": f"Converted {len(converted)} transcript(s)" if converted else None,
    }


if __name__ == "__main__":
    graceful_main(run_hook)

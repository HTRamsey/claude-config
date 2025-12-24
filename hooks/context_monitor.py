#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "tiktoken>=0.7",
# ]
# ///
"""
Context Monitor Hook - Monitors conversation size and suggests compaction.
Runs on UserPromptSubmit to warn when context is getting large.

Uses tiktoken for accurate Claude token counting (cl100k_base encoding).
At critical thresholds:
- Automatically backs up transcript (pre-compact safety)
- Shows a summary of session activity
"""
import json
import os
import sys
from pathlib import Path
from collections import defaultdict

import tiktoken

# Import shared utilities for backup
sys.path.insert(0, str(Path(__file__).parent))
try:
    from hook_utils import backup_transcript, log_event, graceful_main
    HAS_UTILS = True
except ImportError:
    HAS_UTILS = False
    def graceful_main(name):
        def decorator(func):
            return func
        return decorator
    def log_event(*args, **kwargs):
        pass
    def backup_transcript(*args, **kwargs):
        return None

# Configuration
TOKEN_WARNING_THRESHOLD = 40000  # Warn at 40K tokens
TOKEN_CRITICAL_THRESHOLD = 80000  # Strong warning at 80K

# Claude uses cl100k_base encoding (same as GPT-4)
_encoder = None

def get_encoder():
    """Lazy-load encoder to avoid startup cost when not needed."""
    global _encoder
    if _encoder is None:
        _encoder = tiktoken.get_encoding("cl100k_base")
    return _encoder

def count_tokens(text: str) -> int:
    """Accurate token count using tiktoken."""
    if not text:
        return 0
    return len(get_encoder().encode(text))

def get_transcript_size(transcript_path):
    """Read transcript and count tokens accurately."""
    if not transcript_path or not os.path.exists(transcript_path):
        return 0, 0

    # Fast path: check file size first (avoid full scan for small files)
    # ~4 bytes per token on average, 40K tokens ≈ 160KB
    try:
        file_size = os.path.getsize(transcript_path)
        if file_size < 160 * 1024:  # Under 160KB, estimate without full scan
            estimated_tokens = file_size // 4
            estimated_messages = file_size // 500
            return estimated_tokens, estimated_messages
    except OSError:
        pass

    # Full scan with accurate token counting for large files
    total_tokens = 0
    message_count = 0

    try:
        with open(transcript_path, 'r') as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    if 'content' in entry:
                        content = entry['content']
                        if isinstance(content, str):
                            total_tokens += count_tokens(content)
                        elif isinstance(content, list):
                            for item in content:
                                if isinstance(item, dict) and 'text' in item:
                                    total_tokens += count_tokens(item['text'])
                    message_count += 1
                except json.JSONDecodeError:
                    continue
    except Exception:
        return 0, 0

    return total_tokens, message_count

def get_session_summary(transcript_path):
    """Generate brief summary of session activity for compaction guidance."""
    if not transcript_path or not os.path.exists(transcript_path):
        return ""

    files_edited = set()
    files_written = set()
    tool_counts = defaultdict(int)
    error_count = 0

    try:
        with open(transcript_path, 'r') as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    tool = entry.get("tool_name", "")
                    if tool:
                        tool_counts[tool] += 1
                        tool_input = entry.get("tool_input", {})
                        path = tool_input.get("file_path", "")
                        if tool == "Edit" and path:
                            files_edited.add(Path(path).name)
                        elif tool == "Write" and path:
                            files_written.add(Path(path).name)

                    content = str(entry.get("content", ""))
                    if "error" in content.lower() or "failed" in content.lower():
                        error_count += 1
                except json.JSONDecodeError:
                    continue
    except Exception:
        return ""

    # Build compact summary
    parts = []
    if files_edited:
        parts.append(f"Edited: {', '.join(sorted(files_edited)[:5])}")
    if files_written:
        parts.append(f"Created: {', '.join(sorted(files_written)[:3])}")
    if error_count > 0:
        parts.append(f"Errors: {error_count}")

    # Top 3 tools
    top_tools = sorted(tool_counts.items(), key=lambda x: -x[1])[:3]
    if top_tools:
        tools_str = ", ".join(f"{t}:{c}" for t, c in top_tools)
        parts.append(f"Tools: {tools_str}")

    return " | ".join(parts) if parts else ""

@graceful_main("context_monitor")
def main():
    try:
        ctx = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    transcript_path = ctx.get('transcript_path', '')
    token_count, message_count = get_transcript_size(transcript_path)

    if token_count >= TOKEN_CRITICAL_THRESHOLD:
        # Pre-compact backup (audit trail)
        if HAS_UTILS and transcript_path:
            backup_path = backup_transcript(transcript_path, "pre_compact")
            if backup_path:
                log_event("context_monitor", "pre_compact_backup", {
                    "tokens": token_count,
                    "backup": backup_path
                })

        summary = get_session_summary(transcript_path)
        print(f"[Context Monitor] CRITICAL: {token_count:,} tokens ({message_count} msgs)")
        print("  Transcript backed up automatically.")
        if summary:
            print(f"  Session: {summary}")
        print("  Recommend /compact. Preserve: current task, modified files, errors.")

    elif token_count >= TOKEN_WARNING_THRESHOLD:
        print(f"[Context Monitor] {token_count:,} tokens. /compact available if needed.")

    sys.exit(0)

if __name__ == "__main__":
    main()

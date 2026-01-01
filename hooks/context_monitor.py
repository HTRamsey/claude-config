#!/usr/bin/env python3
# Requires: tiktoken (see ~/.claude/pyproject.toml)
"""
Context Monitor Hook - Monitors conversation size and suggests compaction.
Runs on UserPromptSubmit to warn when context is getting large.

Uses tiktoken for accurate Claude token counting (cl100k_base encoding).
At critical thresholds:
- Automatically backs up transcript (pre-compact safety)
- Shows a summary of session activity

Uses cachetools TTLCache for in-memory caching between calls.
"""
import os
import sys
from pathlib import Path
from collections import defaultdict

from cachetools import TTLCache

# Import shared utilities for backup
from hook_utils import backup_transcript, log_event, graceful_main, safe_load_json, safe_save_json
from config import Thresholds, CACHE_DIR

# Configuration (from centralized config)
TOKEN_WARNING_THRESHOLD = Thresholds.TOKEN_WARNING
TOKEN_CRITICAL_THRESHOLD = Thresholds.TOKEN_CRITICAL
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_FILE = CACHE_DIR / "context-cache.json"

# Claude uses cl100k_base encoding (same as GPT-4)
_encoder = None

# TTL cache for file-based token cache (60 second in-memory TTL)
_token_cache: TTLCache = TTLCache(maxsize=10, ttl=60)
_TOKEN_CACHE_KEY = "file_cache"

def get_encoder():
    """Lazy-load encoder to avoid startup cost when not needed."""
    global _encoder
    if _encoder is None:
        import tiktoken  # Lazy import - only when needed for large transcripts
        _encoder = tiktoken.get_encoding("cl100k_base")
    return _encoder

def count_tokens(text: str) -> int:
    """Accurate token count using tiktoken."""
    if not text:
        return 0
    return len(get_encoder().encode(text))

def load_cache():
    """Load token count cache from disk with in-memory caching."""
    if _TOKEN_CACHE_KEY in _token_cache:
        return _token_cache[_TOKEN_CACHE_KEY]
    data = safe_load_json(CACHE_FILE, {})
    _token_cache[_TOKEN_CACHE_KEY] = data
    return data

def save_cache(cache):
    """Save token count cache to disk and update in-memory cache."""
    _token_cache[_TOKEN_CACHE_KEY] = cache
    safe_save_json(CACHE_FILE, cache)

def get_cached_count(transcript_path):
    """Check cache for valid token count. Returns (tokens, messages) or None."""
    cache = load_cache()
    cached = cache.get("transcript")
    if not cached or cached.get("path") != transcript_path:
        return None
    try:
        stat = os.stat(transcript_path)
        if cached.get("mtime") == stat.st_mtime and cached.get("size") == stat.st_size:
            return cached.get("tokens", 0), cached.get("messages", 0)
    except OSError:
        pass
    return None

def update_cache(transcript_path, tokens, messages):
    """Update cache with new token count."""
    try:
        stat = os.stat(transcript_path)
        cache = {
            "transcript": {
                "path": transcript_path,
                "mtime": stat.st_mtime,
                "size": stat.st_size,
                "tokens": tokens,
                "messages": messages
            }
        }
        save_cache(cache)
    except OSError:
        pass

def get_transcript_size(transcript_path):
    """Read transcript and count tokens accurately, with caching."""
    if not transcript_path or not os.path.exists(transcript_path):
        return 0, 0

    # Check cache first (avoids expensive recount if file unchanged)
    cached = get_cached_count(transcript_path)
    if cached:
        return cached

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
    except (OSError, PermissionError):
        return 0, 0

    # Cache the result for next time
    update_cache(transcript_path, total_tokens, message_count)

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
    except (OSError, PermissionError):
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

def check_context(ctx: dict) -> dict | None:
    """Handler function for dispatcher. Returns message dict or None."""
    transcript_path = ctx.get('transcript_path', '')
    token_count, message_count = get_transcript_size(transcript_path)

    if token_count >= TOKEN_CRITICAL_THRESHOLD:
        # Pre-compact backup (audit trail)
        if transcript_path:
            backup_path = backup_transcript(transcript_path, "pre_compact")
            if backup_path:
                log_event("context_monitor", "pre_compact_backup", {
                    "tokens": token_count,
                    "backup": backup_path
                })

        summary = get_session_summary(transcript_path)
        lines = [f"[Context Monitor] CRITICAL: {token_count:,} tokens ({message_count} msgs)"]
        lines.append("  Transcript backed up automatically.")
        if summary:
            lines.append(f"  Session: {summary}")
        lines.append("  Recommend /compact. Preserve: current task, modified files, errors.")
        return {"message": "\n".join(lines)}

    elif token_count >= TOKEN_WARNING_THRESHOLD:
        return {"message": f"[Context Monitor] {token_count:,} tokens. /compact available if needed."}

    return None


@graceful_main("context_monitor")
def main():
    try:
        ctx = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    result = check_context(ctx)
    if result and result.get("message"):
        print(result["message"])

    sys.exit(0)

if __name__ == "__main__":
    main()

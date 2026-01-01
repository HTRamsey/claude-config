#!/home/jonglaser/.claude/data/venv/bin/python3
"""
Transcript utilities - token counting, caching, and session analysis.

Provides:
- Token counting with incremental caching
- Transcript size estimation
- Session activity summary for compaction guidance
"""
import heapq
import json
import os
from pathlib import Path
from collections import defaultdict

from cachetools import TTLCache

from hooks.config import Timeouts, Limits, CACHE_DIR
from hooks.hook_utils import (
    safe_save_json,
    safe_load_json,
    count_tokens_accurate,
)

# Cache setup
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_FILE = CACHE_DIR / "context-cache.json"

# TTL cache for file-based token cache
_token_cache: TTLCache = TTLCache(maxsize=Limits.TOKEN_CACHE_MAXSIZE, ttl=Timeouts.TOKEN_CACHE_TTL)
_TOKEN_CACHE_KEY = "file_cache"


# ==============================================================================
# Token Counting Cache
# ==============================================================================

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
    """Check cache for valid token count.

    Returns:
        (tokens, messages, offset, can_increment) or None
        - can_increment: True if we can do incremental scan from offset
    """
    cache = load_cache()
    cached = cache.get("transcript")
    if not cached or cached.get("path") != transcript_path:
        return None
    try:
        stat = os.stat(transcript_path)
        cached_size = cached.get("size", 0)
        cached_offset = cached.get("offset", 0)

        # Exact match - file unchanged
        if cached.get("mtime") == stat.st_mtime and cached_size == stat.st_size:
            return cached.get("tokens", 0), cached.get("messages", 0), cached_offset, False

        # File grew - can do incremental scan from last offset
        if stat.st_size > cached_size and cached_offset > 0:
            return cached.get("tokens", 0), cached.get("messages", 0), cached_offset, True

    except OSError:
        pass
    return None


def update_cache(transcript_path, tokens, messages, offset):
    """Update cache with new token count and file offset."""
    try:
        stat = os.stat(transcript_path)
        cache = {
            "transcript": {
                "path": transcript_path,
                "mtime": stat.st_mtime,
                "size": stat.st_size,
                "tokens": tokens,
                "messages": messages,
                "offset": offset
            }
        }
        save_cache(cache)
    except OSError:
        pass


# ==============================================================================
# Token Counting
# ==============================================================================

def _count_tokens_in_entry(entry: dict) -> int:
    """Count tokens in a transcript entry."""
    tokens = 0
    if 'content' in entry:
        content = entry['content']
        if isinstance(content, str):
            tokens += count_tokens_accurate(content)
        elif isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and 'text' in item:
                    tokens += count_tokens_accurate(item['text'])
    return tokens


def get_transcript_size(transcript_path):
    """Read transcript and count tokens accurately, with incremental caching."""
    if not transcript_path or not os.path.exists(transcript_path):
        return 0, 0

    # Check cache first
    cached = get_cached_count(transcript_path)
    if cached:
        tokens, messages, offset, can_increment = cached
        if not can_increment:
            # File unchanged, return cached values
            return tokens, messages

        # Incremental scan from last offset
        try:
            with open(transcript_path, 'r') as f:
                f.seek(offset)
                new_tokens = 0
                new_messages = 0
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        new_tokens += _count_tokens_in_entry(entry)
                        new_messages += 1
                    except json.JSONDecodeError:
                        continue
                new_offset = f.tell()

            total_tokens = tokens + new_tokens
            total_messages = messages + new_messages
            update_cache(transcript_path, total_tokens, total_messages, new_offset)
            return total_tokens, total_messages
        except (OSError, PermissionError):
            pass  # Fall through to full scan

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
                    total_tokens += _count_tokens_in_entry(entry)
                    message_count += 1
                except json.JSONDecodeError:
                    continue
            final_offset = f.tell()
    except (OSError, PermissionError):
        return 0, 0

    # Cache the result with file offset for incremental updates
    update_cache(transcript_path, total_tokens, message_count, final_offset)

    return total_tokens, message_count


# ==============================================================================
# Session Activity Summary
# ==============================================================================

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
    top_tools = heapq.nlargest(3, tool_counts.items(), key=lambda x: x[1])
    if top_tools:
        tools_str = ", ".join(f"{t}:{c}" for t, c in top_tools)
        parts.append(f"Tools: {tools_str}")

    return " | ".join(parts) if parts else ""

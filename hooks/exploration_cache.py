#!/home/jonglaser/.claude/venv/bin/python3
"""
Unified Exploration Cache Hook - Handles both lookup and storage.

Runs on:
- PreToolUse (Task): Check cache before spawning exploration agent
- PostToolUse (Task): Save exploration results to cache

Consolidates cache_lookup.py and exploration_cache.py into single hook.
"""
import json
import hashlib
import sys
import time
from pathlib import Path

# Import shared utilities
sys.path.insert(0, str(Path(__file__).parent))
try:
    from hook_utils import graceful_main, log_event
    HAS_UTILS = True
except ImportError:
    HAS_UTILS = False
    def graceful_main(name):
        def decorator(func):
            return func
        return decorator
    def log_event(*args, **kwargs):
        pass

# Configuration
CACHE_DIR = Path("/tmp/claude-exploration-cache")
CACHE_TTL = 3600  # 60 minutes
MAX_CACHE_ENTRIES = 50
SIMILARITY_THRESHOLD = 0.6

def get_cache_key(prompt: str, cwd: str) -> str:
    """Generate cache key from prompt and working directory."""
    content = f"{cwd}:{prompt.lower().strip()}"
    return hashlib.md5(content.encode()).hexdigest()[:12]

def load_cache() -> dict:
    """Load exploration cache, cleaning expired entries."""
    CACHE_DIR.mkdir(exist_ok=True)
    cache_file = CACHE_DIR / "explorations.json"
    if cache_file.exists():
        try:
            with open(cache_file) as f:
                cache = json.load(f)
                now = time.time()
                cache["entries"] = {
                    k: v for k, v in cache.get("entries", {}).items()
                    if now - v.get("timestamp", 0) < CACHE_TTL
                }
                return cache
        except Exception:
            pass
    return {"entries": {}}

def save_cache(cache: dict):
    """Save exploration cache, limiting size."""
    cache_file = CACHE_DIR / "explorations.json"
    entries = cache.get("entries", {})
    if len(entries) > MAX_CACHE_ENTRIES:
        sorted_entries = sorted(entries.items(), key=lambda x: x[1].get("timestamp", 0), reverse=True)
        cache["entries"] = dict(sorted_entries[:MAX_CACHE_ENTRIES])
    try:
        with open(cache_file, "w") as f:
            json.dump(cache, f)
    except Exception:
        pass

def find_similar_exploration(prompt: str, cwd: str, cache: dict) -> dict | None:
    """Find a similar cached exploration (exact or fuzzy match)."""
    now = time.time()
    entries = cache.get("entries", {})

    # Exact match first
    cache_key = get_cache_key(prompt, cwd)
    if cache_key in entries:
        entry = entries[cache_key]
        if now - entry.get("timestamp", 0) < CACHE_TTL:
            return entry

    # Fuzzy match - check keyword overlap
    prompt_words = set(prompt.lower().split())
    best_match = None
    best_score = 0

    for key, entry in entries.items():
        if now - entry.get("timestamp", 0) >= CACHE_TTL:
            continue
        if entry.get("cwd", "") != cwd:
            continue

        cached_words = set(entry.get("prompt", "").lower().split())
        overlap = len(prompt_words & cached_words)
        total = len(prompt_words | cached_words)

        if total > 0:
            score = overlap / total
            if score > SIMILARITY_THRESHOLD and score > best_score:
                best_score = score
                best_match = entry

    return best_match

def handle_pre_tool_use(ctx: dict) -> dict | None:
    """Check cache before spawning exploration agent."""
    tool_input = ctx.get("tool_input", {})
    cwd = ctx.get("cwd", "")

    subagent_type = tool_input.get("subagent_type", "")
    prompt = tool_input.get("prompt", "")

    if subagent_type not in ("Explore", "quick-explorer"):
        return None
    if not prompt:
        return None

    cache = load_cache()
    cached = find_similar_exploration(prompt, cwd, cache)

    if cached:
        age_mins = int((time.time() - cached.get("timestamp", 0)) / 60)
        summary = cached.get("summary", "")[:200]
        log_event("exploration_cache", "cache_hit", {"age_mins": age_mins, "subagent": subagent_type})
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "approve",
                "permissionDecisionReason": f"[Cache Hit] Similar exploration found ({age_mins}m ago): {summary}"
            }
        }
    return None

def handle_post_tool_use(ctx: dict) -> dict | None:
    """Save exploration results to cache."""
    tool_input = ctx.get("tool_input", {})
    tool_result = ctx.get("tool_result", {})
    cwd = ctx.get("cwd", "")

    subagent_type = tool_input.get("subagent_type", "")
    prompt = tool_input.get("prompt", "")

    if subagent_type not in ("Explore", "quick-explorer"):
        return None
    if not prompt:
        return None

    # Extract result content
    result_content = ""
    if isinstance(tool_result, dict):
        result_content = tool_result.get("content", "") or tool_result.get("output", "")
    elif isinstance(tool_result, str):
        result_content = tool_result

    if not result_content:
        return None

    # Truncate to summary
    summary = result_content[:500]
    if len(result_content) > 500:
        summary += "..."

    cache = load_cache()
    cache_key = get_cache_key(prompt, cwd)
    cache["entries"][cache_key] = {
        "prompt": prompt[:100],
        "summary": summary,
        "cwd": cwd,
        "timestamp": time.time(),
        "subagent": subagent_type
    }
    save_cache(cache)
    log_event("exploration_cache", "cached_exploration", {"key": cache_key, "subagent": subagent_type})

    # PostToolUse just needs hookSpecificOutput with message
    return {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "message": f"[Cache] Exploration cached (key: {cache_key})"
        }
    }

@graceful_main("exploration_cache")
def main():
    try:
        ctx = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = ctx.get("tool_name", "")

    if tool_name != "Task":
        sys.exit(0)

    # Detect pre/post based on presence of tool_result
    # PostToolUse has tool_result, PreToolUse doesn't
    result = None
    if "tool_result" in ctx:
        result = handle_post_tool_use(ctx)
    else:
        result = handle_pre_tool_use(ctx)

    if result:
        print(json.dumps(result))

    sys.exit(0)

if __name__ == "__main__":
    main()

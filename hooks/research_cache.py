#!/home/jonglaser/.claude/venv/bin/python3
"""
Research cache for WebFetch - caches fetched content to avoid repeat fetches.

PreToolUse: Check cache, show cached content if fresh
PostToolUse: Store fetched content in cache
"""
import json
import sys
import hashlib
from datetime import datetime, timedelta
from pathlib import Path

# Import shared utilities for logging
sys.path.insert(0, str(Path(__file__).parent))
try:
    from hook_utils import log_event, DATA_DIR, graceful_main
    HAS_UTILS = True
except ImportError:
    HAS_UTILS = False
    DATA_DIR = Path.home() / ".claude" / "data"
    def log_event(*args, **kwargs):
        pass
    def graceful_main(name):
        def decorator(func):
            return func
        return decorator

CACHE_FILE = DATA_DIR / "research-cache.json"
CACHE_TTL_HOURS = 24
MAX_CACHE_ENTRIES = 100
MAX_CONTENT_SIZE = 50000


def get_cache() -> dict:
    """Load cache from disk."""
    try:
        if CACHE_FILE.exists():
            with open(CACHE_FILE) as f:
                return json.load(f)
    except (json.JSONDecodeError, IOError):
        pass
    return {"entries": {}, "stats": {"hits": 0, "misses": 0, "saves": 0}}


def save_cache(cache: dict):
    """Save cache to disk."""
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(CACHE_FILE, 'w') as f:
            json.dump(cache, f, indent=2)
    except IOError:
        pass


def url_key(url: str) -> str:
    """Generate cache key from URL."""
    return hashlib.md5(url.lower().encode()).hexdigest()[:16]


def is_fresh(entry: dict) -> bool:
    """Check if cache entry is still fresh."""
    try:
        cached_at = datetime.fromisoformat(entry["cached_at"])
        return datetime.now() - cached_at < timedelta(hours=CACHE_TTL_HOURS)
    except (KeyError, ValueError):
        return False


def prune_cache(cache: dict):
    """Remove stale entries and limit size."""
    entries = cache.get("entries", {})
    fresh = {k: v for k, v in entries.items() if is_fresh(v)}
    if len(fresh) > MAX_CACHE_ENTRIES:
        sorted_entries = sorted(fresh.items(), key=lambda x: x[1].get("cached_at", ""), reverse=True)
        fresh = dict(sorted_entries[:MAX_CACHE_ENTRIES])
    cache["entries"] = fresh


def handle_pre_tool_use(ctx: dict) -> dict | None:
    """Handler for PreToolUse - check cache."""
    tool_name = ctx.get("tool_name", "")
    tool_input = ctx.get("tool_input", {})

    if tool_name != "WebFetch":
        return None

    url = tool_input.get("url", "")
    if not url:
        return None

    cache = get_cache()
    key = url_key(url)
    entry = cache.get("entries", {}).get(key)

    if entry and is_fresh(entry):
        cache["stats"]["hits"] = cache["stats"].get("hits", 0) + 1
        save_cache(cache)
        log_event("research_cache", "hit", {"url": url[:80]})

        cached_summary = entry.get("summary", "")[:500]
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "permissionDecisionReason": f"[CACHE HIT - {CACHE_TTL_HOURS}h fresh] {url}\n\nCached content:\n{cached_summary}\n\n(Consider skipping fetch if this answers your question)"
            }
        }
    else:
        cache["stats"]["misses"] = cache["stats"].get("misses", 0) + 1
        save_cache(cache)

    return None


def handle_post_tool_use(ctx: dict) -> dict | None:
    """Handler for PostToolUse - store in cache."""
    tool_name = ctx.get("tool_name", "")
    tool_input = ctx.get("tool_input", {})

    if tool_name != "WebFetch":
        return None

    url = tool_input.get("url", "")
    if not url:
        return None

    cache = get_cache()
    key = url_key(url)

    tool_result = ctx.get("tool_result", "")
    content = ""

    if isinstance(tool_result, dict):
        content = tool_result.get("content", "") or tool_result.get("text", "") or str(tool_result)
    elif isinstance(tool_result, str):
        content = tool_result

    if content and len(content) < MAX_CONTENT_SIZE:
        cache.setdefault("entries", {})[key] = {
            "url": url,
            "summary": content[:2000],
            "cached_at": datetime.now().isoformat()
        }
        cache["stats"]["saves"] = cache["stats"].get("saves", 0) + 1
        prune_cache(cache)
        save_cache(cache)
        log_event("research_cache", "save", {"url": url[:80]})

    return None


@graceful_main("research_cache")
def main():
    try:
        ctx = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    # Detect Pre vs Post by checking for tool_result
    if "tool_result" in ctx:
        handle_post_tool_use(ctx)
    else:
        result = handle_pre_tool_use(ctx)
        if result:
            print(json.dumps(result))

    sys.exit(0)


if __name__ == "__main__":
    main()

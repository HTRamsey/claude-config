#!/home/jonglaser/.claude/data/venv/bin/python3
"""
Unified Cache Hook - Handles exploration and research caching.

Consolidates exploration_cache.py and research_cache.py.

Runs on:
- PreToolUse (Task, WebFetch): Check cache before execution
- PostToolUse (Task, WebFetch): Save results to cache
"""
import json
import hashlib
import sys
import time
from pathlib import Path
from dataclasses import dataclass

try:
    from rapidfuzz import fuzz
    HAS_RAPIDFUZZ = True
except ImportError:
    HAS_RAPIDFUZZ = False

sys.path.insert(0, str(Path(__file__).parent))
from config import Timeouts, Thresholds, CACHE_DIR
from hook_utils import graceful_main, log_event

# Ensure cache directory exists
CACHE_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class CacheConfig:
    name: str
    file: Path
    ttl_seconds: int
    max_entries: int
    fuzzy_match: bool = False
    similarity_threshold: float = 0.6


CACHES = {
    "exploration": CacheConfig(
        name="exploration",
        file=CACHE_DIR / "exploration-cache.json",
        ttl_seconds=Timeouts.EXPLORATION_CACHE_TTL,
        max_entries=Thresholds.MAX_CACHE_ENTRIES,
        fuzzy_match=True,
        similarity_threshold=0.6
    ),
    "research": CacheConfig(
        name="research",
        file=CACHE_DIR / "research-cache.json",
        ttl_seconds=Timeouts.RESEARCH_CACHE_TTL,
        max_entries=Thresholds.MAX_CACHE_ENTRIES,
        fuzzy_match=False
    )
}


def load_cache(cfg: CacheConfig) -> dict:
    """Load cache, cleaning expired entries."""
    cfg.file.parent.mkdir(parents=True, exist_ok=True)
    if cfg.file.exists():
        try:
            with open(cfg.file) as f:
                cache = json.load(f)
                now = time.time()
                cache["entries"] = {
                    k: v for k, v in cache.get("entries", {}).items()
                    if now - v.get("timestamp", 0) < cfg.ttl_seconds
                }
                return cache
        except Exception:
            pass
    return {"entries": {}, "stats": {"hits": 0, "misses": 0, "saves": 0}}


def save_cache(cfg: CacheConfig, cache: dict):
    """Save cache, limiting size."""
    entries = cache.get("entries", {})
    if len(entries) > cfg.max_entries:
        sorted_entries = sorted(
            entries.items(),
            key=lambda x: x[1].get("timestamp", 0),
            reverse=True
        )
        cache["entries"] = dict(sorted_entries[:cfg.max_entries])
    try:
        with open(cfg.file, "w") as f:
            json.dump(cache, f)
    except Exception:
        pass


def get_cache_key(content: str) -> str:
    """Generate cache key from content."""
    return hashlib.md5(content.lower().encode()).hexdigest()[:16]


def find_fuzzy_match(prompt: str, cwd: str, cache: dict, cfg: CacheConfig) -> dict | None:
    """Find similar cached entry using fuzzy matching.

    Optimized with:
    - Index by first word for O(1) candidate filtering
    - Early termination for high-confidence matches (>0.9)
    - Limit search to most recent N entries
    - Memoization of prompt words for non-rapidfuzz fallback
    """
    now = time.time()
    entries = cache.get("entries", {})
    prompt_lower = prompt.lower()
    prompt_first_word = prompt_lower.split()[0] if prompt_lower.split() else ""
    best_match = None
    best_score = 0

    # Pre-compute for fallback matching
    prompt_words = None if HAS_RAPIDFUZZ else set(prompt_lower.split())

    # Sort by timestamp (most recent first) and limit candidates
    sorted_entries = sorted(
        entries.values(),
        key=lambda e: e.get("timestamp", 0),
        reverse=True
    )[:30]  # Limit to 30 most recent entries

    for entry in sorted_entries:
        if now - entry.get("timestamp", 0) >= cfg.ttl_seconds:
            continue
        if entry.get("cwd", "") != cwd:
            continue

        cached_prompt = entry.get("prompt", "").lower()

        # Quick filter: skip if first words don't match (cheap check)
        cached_first_word = cached_prompt.split()[0] if cached_prompt.split() else ""
        if prompt_first_word and cached_first_word and prompt_first_word != cached_first_word:
            # Allow through if they share significant words (more expensive check)
            if not HAS_RAPIDFUZZ:
                cached_words = set(cached_prompt.split())
                if len(prompt_words & cached_words) < 2:
                    continue

        if HAS_RAPIDFUZZ:
            score = fuzz.ratio(prompt_lower, cached_prompt) / 100.0
        else:
            cached_words = set(cached_prompt.split())
            overlap = len(prompt_words & cached_words)
            total = len(prompt_words | cached_words)
            score = overlap / total if total > 0 else 0

        if score > cfg.similarity_threshold and score > best_score:
            best_score = score
            best_match = entry
            # Early termination for high-confidence matches
            if score >= 0.9:
                return best_match

    return best_match


def handle_exploration_pre(ctx: dict) -> dict | None:
    """Check exploration cache before spawning agent."""
    tool_input = ctx.get("tool_input", {})
    cwd = ctx.get("cwd", "")
    subagent_type = tool_input.get("subagent_type", "")
    prompt = tool_input.get("prompt", "")

    if subagent_type not in ("Explore", "quick-lookup") or not prompt:
        return None

    cfg = CACHES["exploration"]
    cache = load_cache(cfg)

    # Exact match
    cache_key = get_cache_key(f"{cwd}:{prompt}")
    entry = cache.get("entries", {}).get(cache_key)
    now = time.time()

    if entry and now - entry.get("timestamp", 0) < cfg.ttl_seconds:
        age_mins = int((now - entry["timestamp"]) / 60)
        summary = entry.get("summary", "")[:200]
        cache["stats"]["hits"] = cache["stats"].get("hits", 0) + 1
        save_cache(cfg, cache)
        log_event("unified_cache", "exploration_hit", {"age_mins": age_mins})
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "permissionDecisionReason": f"[Cache Hit] Similar exploration found ({age_mins}m ago): {summary}"
            }
        }

    # Fuzzy match
    if cfg.fuzzy_match:
        matched = find_fuzzy_match(prompt, cwd, cache, cfg)
        if matched:
            age_mins = int((now - matched.get("timestamp", 0)) / 60)
            summary = matched.get("summary", "")[:200]
            cache["stats"]["hits"] = cache["stats"].get("hits", 0) + 1
            save_cache(cfg, cache)
            log_event("unified_cache", "exploration_fuzzy_hit", {"age_mins": age_mins})
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "allow",
                    "permissionDecisionReason": f"[Cache Hit] Similar exploration found ({age_mins}m ago): {summary}"
                }
            }

    cache["stats"]["misses"] = cache["stats"].get("misses", 0) + 1
    save_cache(cfg, cache)
    return None


def handle_exploration_post(ctx: dict) -> dict | None:
    """Save exploration results to cache."""
    tool_input = ctx.get("tool_input", {})
    # Claude Code uses "tool_response" for PostToolUse hooks
    tool_result = ctx.get("tool_response") or ctx.get("tool_result", {})
    cwd = ctx.get("cwd", "")
    subagent_type = tool_input.get("subagent_type", "")
    prompt = tool_input.get("prompt", "")

    if subagent_type not in ("Explore", "quick-lookup") or not prompt:
        return None

    result_content = ""
    if isinstance(tool_result, dict):
        result_content = tool_result.get("content", "") or tool_result.get("output", "")
    elif isinstance(tool_result, str):
        result_content = tool_result

    if not result_content:
        return None

    cfg = CACHES["exploration"]
    cache = load_cache(cfg)
    cache_key = get_cache_key(f"{cwd}:{prompt}")

    cache["entries"][cache_key] = {
        "prompt": prompt[:100],
        "summary": result_content[:500] + ("..." if len(result_content) > 500 else ""),
        "cwd": cwd,
        "timestamp": time.time(),
        "subagent": subagent_type
    }
    cache["stats"]["saves"] = cache["stats"].get("saves", 0) + 1
    save_cache(cfg, cache)
    log_event("unified_cache", "exploration_saved", {"key": cache_key})
    return None


def handle_research_pre(ctx: dict) -> dict | None:
    """Check research cache before WebFetch."""
    tool_input = ctx.get("tool_input", {})
    url = tool_input.get("url", "")

    if not url:
        return None

    cfg = CACHES["research"]
    cache = load_cache(cfg)
    cache_key = get_cache_key(url)
    entry = cache.get("entries", {}).get(cache_key)
    now = time.time()

    if entry and now - entry.get("timestamp", 0) < cfg.ttl_seconds:
        cache["stats"]["hits"] = cache["stats"].get("hits", 0) + 1
        save_cache(cfg, cache)
        log_event("unified_cache", "research_hit", {"url": url[:80]})

        cached_summary = entry.get("summary", "")[:500]
        ttl_hours = cfg.ttl_seconds // 3600
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "permissionDecisionReason": f"[CACHE HIT - {ttl_hours}h fresh] {url}\n\nCached content:\n{cached_summary}\n\n(Consider skipping fetch if this answers your question)"
            }
        }

    cache["stats"]["misses"] = cache["stats"].get("misses", 0) + 1
    save_cache(cfg, cache)
    return None


def handle_research_post(ctx: dict) -> dict | None:
    """Save WebFetch results to cache."""
    tool_input = ctx.get("tool_input", {})
    # Claude Code uses "tool_response" for PostToolUse hooks
    tool_result = ctx.get("tool_response") or ctx.get("tool_result", "")
    url = tool_input.get("url", "")

    if not url:
        log_event("unified_cache", "research_skip", {"reason": "no_url"})
        return None

    content = ""
    if isinstance(tool_result, dict):
        content = tool_result.get("content", "") or tool_result.get("text", "") or str(tool_result)
    elif isinstance(tool_result, str):
        content = tool_result

    if not content:
        log_event("unified_cache", "research_skip", {"reason": "no_content", "url": url[:80]})
        return None
    if len(content) > 50000:
        log_event("unified_cache", "research_skip", {"reason": "too_large", "size": len(content), "url": url[:80]})
        return None

    cfg = CACHES["research"]
    cache = load_cache(cfg)
    cache_key = get_cache_key(url)

    cache["entries"][cache_key] = {
        "url": url,
        "summary": content[:2000],
        "timestamp": time.time()
    }
    cache["stats"]["saves"] = cache["stats"].get("saves", 0) + 1
    save_cache(cfg, cache)
    log_event("unified_cache", "research_saved", {"url": url[:80]})
    return None


@graceful_main("unified_cache")
def main():
    try:
        ctx = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = ctx.get("tool_name", "")
    # Claude Code uses "tool_response" for PostToolUse hooks
    is_post = "tool_response" in ctx or "tool_result" in ctx

    result = None

    if tool_name == "Task":
        result = handle_exploration_post(ctx) if is_post else handle_exploration_pre(ctx)
    elif tool_name == "WebFetch":
        result = handle_research_post(ctx) if is_post else handle_research_pre(ctx)

    if result:
        print(json.dumps(result))

    sys.exit(0)


if __name__ == "__main__":
    main()

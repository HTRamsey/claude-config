#!/home/jonglaser/.claude/data/venv/bin/python3
"""
Unified Cache Hook - Handles exploration and research caching.

Consolidates exploration_cache.py and research_cache.py.

Runs on:
- PreToolUse (Task, WebFetch): Check cache before execution
- PostToolUse (Task, WebFetch): Save results to cache
"""
import heapq
import json
import hashlib
import sys
import time
from pathlib import Path
from dataclasses import dataclass

try:
    from rapidfuzz import fuzz, process
    HAS_RAPIDFUZZ = True
except ImportError:
    HAS_RAPIDFUZZ = False

from config import Timeouts, Thresholds, Limits, CACHE_DIR
from hook_utils import graceful_main, log_event, is_post_tool_use
from hook_sdk import PreToolUseContext, PostToolUseContext, Response

# Ensure cache directory exists
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# In-memory stats buffer to avoid disk writes on cache misses
# Only flush to disk when actual cache entries are saved
_stats_buffer: dict[str, dict[str, int]] = {}
_STATS_FLUSH_INTERVAL = 10  # Flush stats every N saves


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
        except (json.JSONDecodeError, IOError, OSError, KeyError, TypeError) as e:
            log_event("unified_cache", "load_error", {"file": str(cfg.file), "error": str(e)}, "warning")
    return {"entries": {}, "stats": {"hits": 0, "misses": 0, "saves": 0}}


def _update_stat(cache_name: str, stat_name: str, increment: int = 1):
    """Update stats in memory buffer (no disk I/O)."""
    if cache_name not in _stats_buffer:
        _stats_buffer[cache_name] = {}
    _stats_buffer[cache_name][stat_name] = _stats_buffer[cache_name].get(stat_name, 0) + increment


def _flush_stats(cache: dict, cache_name: str):
    """Merge buffered stats into cache dict."""
    if cache_name in _stats_buffer:
        for stat_name, value in _stats_buffer[cache_name].items():
            cache["stats"][stat_name] = cache["stats"].get(stat_name, 0) + value
        _stats_buffer[cache_name] = {}


def save_cache(cfg: CacheConfig, cache: dict):
    """Save cache, limiting size with O(k log n) eviction using heapq.

    Also flushes buffered stats to avoid separate disk writes for stats updates.
    """
    # Flush any buffered stats
    _flush_stats(cache, cfg.name)

    entries = cache.get("entries", {})
    if len(entries) > cfg.max_entries:
        # Use heapq.nlargest for O(k log n) instead of O(n log n) full sort
        top_entries = heapq.nlargest(
            cfg.max_entries,
            entries.items(),
            key=lambda x: x[1].get("timestamp", 0)
        )
        cache["entries"] = dict(top_entries)
    try:
        with open(cfg.file, "w") as f:
            json.dump(cache, f)
    except (IOError, OSError, TypeError) as e:
        log_event("unified_cache", "save_error", {"file": str(cfg.file), "error": str(e)}, "warning")


def get_cache_key(content: str) -> str:
    """Generate cache key from content."""
    return hashlib.md5(content.lower().encode()).hexdigest()[:16]


def find_fuzzy_match(prompt: str, cwd: str, cache: dict, cfg: CacheConfig) -> dict | None:
    """Find similar cached entry using fuzzy matching.

    Optimized with rapidfuzz.process.extractOne() for ~5x speedup:
    - Uses internal C loop instead of Python iteration
    - Pre-filters by TTL and cwd before fuzzy matching
    - score_cutoff eliminates low-scoring comparisons early
    """
    now = time.time()
    entries = cache.get("entries", {})
    prompt_lower = prompt.lower()

    # Pre-filter valid candidates (TTL + cwd match)
    candidates = []
    candidate_map = {}  # prompt -> entry for lookup after match
    for key, entry in entries.items():
        if now - entry.get("timestamp", 0) >= cfg.ttl_seconds:
            continue
        if entry.get("cwd", "") != cwd:
            continue
        cached_prompt = entry.get("prompt", "").lower()
        if cached_prompt:
            candidates.append(cached_prompt)
            candidate_map[cached_prompt] = entry

    if not candidates:
        return None

    # Limit to most recent entries using heapq for O(k log n)
    max_entries = Limits.MAX_FUZZY_SEARCH_ENTRIES
    if len(candidates) > max_entries:
        top_items = heapq.nlargest(
            max_entries,
            candidate_map.items(),
            key=lambda x: x[1].get("timestamp", 0)
        )
        candidates = [p for p, _ in top_items]
        candidate_map = dict(top_items)

    threshold_pct = int(cfg.similarity_threshold * 100)

    if HAS_RAPIDFUZZ:
        # Use extractOne for ~5x faster matching (internal C loop)
        result = process.extractOne(
            prompt_lower,
            candidates,
            scorer=fuzz.ratio,
            score_cutoff=threshold_pct
        )
        if result:
            matched_prompt, score, _ = result
            return candidate_map.get(matched_prompt)
    else:
        # Fallback: word overlap matching
        prompt_words = set(prompt_lower.split())
        best_match = None
        best_score = 0

        for cached_prompt in candidates:
            cached_words = set(cached_prompt.split())
            overlap = len(prompt_words & cached_words)
            total = len(prompt_words | cached_words)
            score = overlap / total if total > 0 else 0

            if score > cfg.similarity_threshold and score > best_score:
                best_score = score
                best_match = candidate_map.get(cached_prompt)

        return best_match

    return None


def handle_exploration_pre(raw: dict) -> dict | None:
    """Check exploration cache before spawning agent."""
    ctx = PreToolUseContext(raw)
    subagent_type = ctx.tool_input.subagent_type
    prompt = ctx.tool_input.prompt

    if subagent_type not in ("Explore", "quick-lookup") or not prompt:
        return None

    cwd = ctx.cwd

    cfg = CACHES["exploration"]
    cache = load_cache(cfg)

    # Exact match
    cache_key = get_cache_key(f"{cwd}:{prompt}")
    entry = cache.get("entries", {}).get(cache_key)
    now = time.time()

    if entry and now - entry.get("timestamp", 0) < cfg.ttl_seconds:
        age_mins = int((now - entry["timestamp"]) / 60)
        summary = entry.get("summary", "")[:200]
        _update_stat(cfg.name, "hits")
        log_event("unified_cache", "exploration_hit", {"age_mins": age_mins})
        return Response.allow(f"[Cache Hit] Similar exploration found ({age_mins}m ago): {summary}")

    # Fuzzy match
    if cfg.fuzzy_match:
        matched = find_fuzzy_match(prompt, cwd, cache, cfg)
        if matched:
            age_mins = int((now - matched.get("timestamp", 0)) / 60)
            summary = matched.get("summary", "")[:200]
            _update_stat(cfg.name, "hits")
            log_event("unified_cache", "exploration_fuzzy_hit", {"age_mins": age_mins})
            return Response.allow(f"[Cache Hit] Similar exploration found ({age_mins}m ago): {summary}")

    # Buffer miss stat - don't save to disk (stats flushed on next cache save)
    _update_stat(cfg.name, "misses")
    return None


def handle_exploration_post(raw: dict) -> dict | None:
    """Save exploration results to cache."""
    ctx = PostToolUseContext(raw)
    subagent_type = ctx.tool_input.subagent_type
    prompt = ctx.tool_input.prompt

    if subagent_type not in ("Explore", "quick-lookup") or not prompt:
        return None

    cwd = ctx.cwd
    tool_result = ctx.tool_result.raw

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


def handle_research_pre(raw: dict) -> dict | None:
    """Check research cache before WebFetch."""
    ctx = PreToolUseContext(raw)
    url = ctx.tool_input.url

    if not url:
        return None

    cfg = CACHES["research"]
    cache = load_cache(cfg)
    cache_key = get_cache_key(url)
    entry = cache.get("entries", {}).get(cache_key)
    now = time.time()

    if entry and now - entry.get("timestamp", 0) < cfg.ttl_seconds:
        _update_stat(cfg.name, "hits")
        log_event("unified_cache", "research_hit", {"url": url[:80]})

        cached_summary = entry.get("summary", "")[:500]
        ttl_hours = cfg.ttl_seconds // 3600
        return Response.allow(f"[CACHE HIT - {ttl_hours}h fresh] {url}\n\nCached content:\n{cached_summary}\n\n(Consider skipping fetch if this answers your question)")

    # Buffer miss stat - don't save to disk (stats flushed on next cache save)
    _update_stat(cfg.name, "misses")
    return None


def handle_research_post(raw: dict) -> dict | None:
    """Save WebFetch results to cache."""
    ctx = PostToolUseContext(raw)
    url = ctx.tool_input.url

    if not url:
        log_event("unified_cache", "research_skip", {"reason": "no_url"})
        return None

    tool_result = ctx.tool_result.raw
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
    is_post = is_post_tool_use(ctx)

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

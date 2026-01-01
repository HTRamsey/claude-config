#!/home/jonglaser/.claude/data/venv/bin/python3
"""
Unified Cache Hook - Handles exploration and research caching.

Uses diskcache for efficient storage with automatic TTL and size management.

Runs on:
- PreToolUse (Task, WebFetch): Check cache before execution
- PostToolUse (Task, WebFetch): Save results to cache
"""
import hashlib
import time
from dataclasses import dataclass

from diskcache import Cache
from rapidfuzz import fuzz, process

from hooks.config import Timeouts, Thresholds, Limits, CACHE_DIR
from hooks.hook_utils import log_event
from hooks.hook_sdk import PreToolUseContext, PostToolUseContext, Response

# Cache directories
EXPLORATION_CACHE_DIR = CACHE_DIR / "exploration"
RESEARCH_CACHE_DIR = CACHE_DIR / "research"
STATS_CACHE_DIR = CACHE_DIR / "stats"


@dataclass
class CacheConfig:
    name: str
    ttl_seconds: int
    max_entries: int
    fuzzy_match: bool = False
    similarity_threshold: float = 0.6


CACHE_CONFIGS = {
    "exploration": CacheConfig(
        name="exploration",
        ttl_seconds=Timeouts.EXPLORATION_CACHE_TTL,
        max_entries=Thresholds.MAX_CACHE_ENTRIES,
        fuzzy_match=True,
        similarity_threshold=0.6
    ),
    "research": CacheConfig(
        name="research",
        ttl_seconds=Timeouts.RESEARCH_CACHE_TTL,
        max_entries=Thresholds.MAX_CACHE_ENTRIES,
        fuzzy_match=False
    )
}

# Lazy-initialized caches
_caches: dict[str, Cache] = {}


def _get_cache(name: str) -> Cache:
    """Get or create a cache instance."""
    if name not in _caches:
        cfg = CACHE_CONFIGS[name]
        cache_dir = EXPLORATION_CACHE_DIR if name == "exploration" else RESEARCH_CACHE_DIR
        _caches[name] = Cache(
            str(cache_dir),
            size_limit=cfg.max_entries * 10000,  # ~10KB per entry estimate
            eviction_policy="least-recently-used",
        )
    return _caches[name]


def _get_stats_cache() -> Cache:
    """Get stats cache."""
    if "stats" not in _caches:
        _caches["stats"] = Cache(str(STATS_CACHE_DIR))
    return _caches["stats"]


def get_cache_key(content: str) -> str:
    """Generate cache key from content."""
    return hashlib.md5(content.lower().encode()).hexdigest()[:16]


def _update_stat(cache_name: str, stat_name: str, increment: int = 1):
    """Update stats in cache."""
    try:
        stats = _get_stats_cache()
        key = f"{cache_name}:{stat_name}"
        current = stats.get(key, 0)
        stats.set(key, current + increment)
    except Exception:
        pass  # Stats are not critical


def get_exploration_entry(cache_key: str, cfg: CacheConfig) -> dict | None:
    """Get exploration cache entry by key."""
    cache = _get_cache("exploration")
    entry = cache.get(cache_key)

    if entry and isinstance(entry, dict):
        # Check TTL manually since we want fine-grained control
        if time.time() - entry.get("timestamp", 0) < cfg.ttl_seconds:
            return entry
        # Expired - delete it
        cache.delete(cache_key)

    return None


def save_exploration_entry(cache_key: str, entry: dict, cfg: CacheConfig):
    """Save exploration cache entry."""
    try:
        cache = _get_cache("exploration")
        cache.set(cache_key, entry, expire=cfg.ttl_seconds)
    except Exception as e:
        log_event("unified_cache", "save_error", {"error": str(e)}, "warning")


def get_research_entry(cache_key: str, cfg: CacheConfig) -> dict | None:
    """Get research cache entry by key."""
    cache = _get_cache("research")
    entry = cache.get(cache_key)

    if entry and isinstance(entry, dict):
        if time.time() - entry.get("timestamp", 0) < cfg.ttl_seconds:
            return entry
        cache.delete(cache_key)

    return None


def save_research_entry(cache_key: str, entry: dict, cfg: CacheConfig):
    """Save research cache entry."""
    try:
        cache = _get_cache("research")
        cache.set(cache_key, entry, expire=cfg.ttl_seconds)
    except Exception as e:
        log_event("unified_cache", "save_error", {"error": str(e)}, "warning")


def find_fuzzy_match(prompt: str, cwd: str, cfg: CacheConfig) -> dict | None:
    """Find similar cached entry using fuzzy matching."""
    cache = _get_cache("exploration")
    now = time.time()
    cutoff = now - cfg.ttl_seconds

    # Iterate through cache entries for this cwd
    candidates = []
    candidate_map = {}

    for key in cache.iterkeys():
        entry = cache.get(key)
        if not entry or not isinstance(entry, dict):
            continue

        # Filter by cwd and TTL
        if entry.get("cwd") != cwd:
            continue
        if entry.get("timestamp", 0) < cutoff:
            continue

        cached_prompt = (entry.get("prompt") or "").lower()
        if cached_prompt:
            candidates.append(cached_prompt)
            candidate_map[cached_prompt] = entry

        if len(candidates) >= Limits.MAX_FUZZY_SEARCH_ENTRIES:
            break

    if not candidates:
        return None

    prompt_lower = prompt.lower()
    threshold_pct = int(cfg.similarity_threshold * 100)
    result = process.extractOne(
        prompt_lower,
        candidates,
        scorer=fuzz.ratio,
        score_cutoff=threshold_pct
    )

    if result:
        matched_prompt, score, _ = result
        return candidate_map.get(matched_prompt)

    return None


def handle_exploration_pre(raw: dict) -> dict | None:
    """Check exploration cache before spawning agent."""
    ctx = PreToolUseContext(raw)
    subagent_type = ctx.tool_input.subagent_type
    prompt = ctx.tool_input.prompt

    if subagent_type not in ("Explore", "quick-lookup") or not prompt:
        return None

    cwd = ctx.cwd
    cfg = CACHE_CONFIGS["exploration"]

    # Exact match
    cache_key = get_cache_key(f"{cwd}:{prompt}")
    entry = get_exploration_entry(cache_key, cfg)
    now = time.time()

    if entry:
        age_mins = int((now - entry["timestamp"]) / 60)
        summary = (entry.get("summary") or "")[:200]
        _update_stat(cfg.name, "hits")
        log_event("unified_cache", "exploration_hit", {"age_mins": age_mins})
        return Response.allow(f"[Cache Hit] Similar exploration found ({age_mins}m ago): {summary}")

    # Fuzzy match
    if cfg.fuzzy_match:
        matched = find_fuzzy_match(prompt, cwd, cfg)
        if matched:
            age_mins = int((now - matched["timestamp"]) / 60)
            summary = (matched.get("summary") or "")[:200]
            _update_stat(cfg.name, "hits")
            log_event("unified_cache", "exploration_fuzzy_hit", {"age_mins": age_mins})
            return Response.allow(f"[Cache Hit] Similar exploration found ({age_mins}m ago): {summary}")

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
    result_content = ctx.tool_result.content

    if not result_content:
        return None

    cfg = CACHE_CONFIGS["exploration"]
    cache_key = get_cache_key(f"{cwd}:{prompt}")

    entry = {
        "prompt": prompt[:100],
        "summary": result_content[:500] + ("..." if len(result_content) > 500 else ""),
        "cwd": cwd,
        "timestamp": time.time(),
        "subagent": subagent_type
    }
    save_exploration_entry(cache_key, entry, cfg)
    _update_stat(cfg.name, "saves")
    log_event("unified_cache", "exploration_saved", {"key": cache_key})
    return None


def handle_research_pre(raw: dict) -> dict | None:
    """Check research cache before WebFetch."""
    ctx = PreToolUseContext(raw)
    url = ctx.tool_input.url

    if not url:
        return None

    cfg = CACHE_CONFIGS["research"]
    cache_key = get_cache_key(url)
    entry = get_research_entry(cache_key, cfg)
    now = time.time()

    if entry:
        _update_stat(cfg.name, "hits")
        log_event("unified_cache", "research_hit", {"url": url[:80]})

        cached_summary = (entry.get("summary") or "")[:500]
        ttl_hours = cfg.ttl_seconds // 3600
        return Response.allow(f"[CACHE HIT - {ttl_hours}h fresh] {url}\n\nCached content:\n{cached_summary}\n\n(Consider skipping fetch if this answers your question)")

    _update_stat(cfg.name, "misses")
    return None


def handle_research_post(raw: dict) -> dict | None:
    """Save WebFetch results to cache."""
    ctx = PostToolUseContext(raw)
    url = ctx.tool_input.url

    if not url:
        log_event("unified_cache", "research_skip", {"reason": "no_url"})
        return None

    content = ctx.tool_result.content

    if not content:
        log_event("unified_cache", "research_skip", {"reason": "no_content", "url": url[:80]})
        return None
    if len(content) > 50000:
        log_event("unified_cache", "research_skip", {"reason": "too_large", "size": len(content), "url": url[:80]})
        return None

    cfg = CACHE_CONFIGS["research"]
    cache_key = get_cache_key(url)

    entry = {
        "url": url,
        "summary": content[:2000],
        "timestamp": time.time()
    }
    save_research_entry(cache_key, entry, cfg)
    _update_stat(cfg.name, "saves")
    log_event("unified_cache", "research_saved", {"url": url[:80]})
    return None

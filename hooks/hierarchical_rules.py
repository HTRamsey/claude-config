#!/home/jonglaser/.claude/data/venv/bin/python3
"""
Hierarchical Rules Hook - Apply per-directory rule overrides.

PreToolUse hook that checks for directory-specific CLAUDE.md files
and applies rules based on the file being accessed.

Supports:
- CLAUDE.md files in any directory (closest to target file wins)
- YAML frontmatter with `paths` patterns for selective application
- Rule inheritance (child directories can override parent rules)

Example CLAUDE.md with path-specific rules:
```yaml
---
paths: src/api/**/*.ts
---
# API Rules
- All endpoints must validate input
- Use `backend-architect` agent for new endpoints
```

Uses cachetools TTLCache for automatic expiration and LRU eviction.
"""
import fnmatch
import json
import os
import re
import sys
import threading
from functools import lru_cache
from pathlib import Path

from cachetools import TTLCache

from hook_utils import graceful_main, log_event, read_state, write_state
from hook_sdk import Response
from config import Timeouts

# TTL cache for directory hierarchy lookups (automatic expiration and LRU eviction)
_hierarchy_cache: TTLCache = TTLCache(maxsize=256, ttl=Timeouts.HIERARCHY_CACHE_TTL)
_hierarchy_cache_lock = threading.Lock()


def parse_frontmatter(content: str) -> tuple[dict, str]:
    """
    Parse YAML frontmatter from markdown content.

    Returns:
        (frontmatter_dict, remaining_content)
    """
    if not content.startswith("---"):
        return {}, content

    lines = content.split("\n")
    end_idx = -1

    for i, line in enumerate(lines[1:], 1):
        if line.strip() == "---":
            end_idx = i
            break

    if end_idx == -1:
        return {}, content

    frontmatter_lines = lines[1:end_idx]
    remaining = "\n".join(lines[end_idx + 1:])

    # Simple YAML parsing (key: value)
    frontmatter = {}
    for line in frontmatter_lines:
        if ":" in line:
            key, _, value = line.partition(":")
            frontmatter[key.strip()] = value.strip().strip('"').strip("'")

    return frontmatter, remaining


@lru_cache(maxsize=256)
def _compile_glob_pattern(pattern: str) -> re.Pattern:
    """Convert glob pattern to compiled regex (cached)."""
    regex = pattern.replace(".", r"\.")
    regex = regex.replace("**", "<<<DOUBLE>>>")
    regex = regex.replace("*", "[^/]*")
    regex = regex.replace("<<<DOUBLE>>>", ".*")
    regex = "^" + regex + "$"
    return re.compile(regex)


def matches_path_pattern(file_path: str, pattern: str) -> bool:
    """
    Check if file_path matches a glob-like pattern.

    Supports:
    - **/*.ts - matches any .ts file in any subdirectory
    - src/**/* - matches anything under src/
    - {src,lib}/**/*.ts - matches .ts in src/ or lib/
    """
    # Handle brace expansion {a,b}
    if "{" in pattern and "}" in pattern:
        match = re.match(r"(.*)\{([^}]+)\}(.*)", pattern)
        if match:
            prefix, options, suffix = match.groups()
            for option in options.split(","):
                expanded = prefix + option.strip() + suffix
                if matches_path_pattern(file_path, expanded):
                    return True
            return False

    # Use cached compiled pattern
    compiled = _compile_glob_pattern(pattern)
    return bool(compiled.match(file_path))


def find_claude_files(start_dir: str, stop_at: str = None) -> list[tuple[str, str]]:
    """
    Find CLAUDE.md files from start_dir up to stop_at (or root).

    Returns:
        List of (directory, content) tuples, closest first

    Uses TTLCache for automatic expiration (no manual pruning needed).
    Thread-safe via _hierarchy_cache_lock.
    """
    cache_key = f"{start_dir}:{stop_at or '/'}"

    # Check cache (with lock)
    with _hierarchy_cache_lock:
        if cache_key in _hierarchy_cache:
            return _hierarchy_cache[cache_key]

    # Filesystem walk (outside lock to avoid blocking other threads)
    results = []
    current = Path(start_dir).resolve()
    stop = Path(stop_at).resolve() if stop_at else Path("/")

    while current >= stop:
        claude_file = current / "CLAUDE.md"
        if claude_file.exists():
            try:
                content = claude_file.read_text()
                results.append((str(current), content))
            except (OSError, PermissionError):
                pass

        # Also check .claude/rules/ directory
        rules_dir = current / ".claude" / "rules"
        if rules_dir.exists():
            for rule_file in sorted(rules_dir.glob("*.md")):
                try:
                    content = rule_file.read_text()
                    results.append((str(current), content))
                except (OSError, PermissionError):
                    pass

        if current == current.parent:
            break
        current = current.parent

    # Update cache (TTLCache handles expiration and LRU eviction automatically)
    with _hierarchy_cache_lock:
        _hierarchy_cache[cache_key] = results

    return results


def get_applicable_rules(file_path: str, cwd: str) -> list[dict]:
    """
    Get all rules applicable to a file path.

    Returns:
        List of rule dicts: {source, frontmatter, content}
    """
    if not file_path:
        return []

    # Resolve file path
    if not os.path.isabs(file_path):
        file_path = os.path.join(cwd, file_path)
    file_path = os.path.normpath(file_path)

    # Get directory of the file
    file_dir = os.path.dirname(file_path)

    # Find CLAUDE.md files
    claude_files = find_claude_files(file_dir, cwd)

    applicable = []
    for source_dir, content in claude_files:
        frontmatter, body = parse_frontmatter(content)

        # Check if this rule applies to our file
        paths_pattern = frontmatter.get("paths", "")
        if paths_pattern:
            # Make file path relative to source dir for matching
            try:
                rel_path = os.path.relpath(file_path, source_dir)
            except ValueError:
                continue

            if not matches_path_pattern(rel_path, paths_pattern):
                continue

        applicable.append({
            "source": source_dir,
            "frontmatter": frontmatter,
            "content": body[:2000],  # Truncate for context
        })

    return applicable


def format_rules_message(rules: list[dict]) -> str:
    """Format rules for message output."""
    if not rules:
        return ""

    parts = []
    for rule in rules[:3]:  # Max 3 rule sources
        source = rule["source"]
        # Extract key points from content (first few lines with bullets/headers)
        content = rule["content"]
        key_lines = []
        for line in content.split("\n"):
            line = line.strip()
            if line.startswith(("#", "-", "*", "1.", "2.", "3.")):
                key_lines.append(line)
                if len(key_lines) >= 3:
                    break

        if key_lines:
            parts.append(f"[{source}] {'; '.join(key_lines)}")

    return " | ".join(parts)


def check_hierarchical_rules(ctx: dict) -> dict | None:
    """
    Handler function for dispatcher.
    Checks for path-specific rules and returns message if found.
    """
    tool_name = ctx.get("tool_name", "")
    tool_input = ctx.get("tool_input", {})
    cwd = ctx.get("cwd", os.getcwd())

    # Only apply to file operations
    if tool_name not in ("Read", "Write", "Edit"):
        return None

    file_path = tool_input.get("file_path", "")
    if not file_path:
        return None

    # Get applicable rules
    rules = get_applicable_rules(file_path, cwd)

    if not rules:
        return None

    # Format message
    message = format_rules_message(rules)
    if not message:
        return None

    log_event("hierarchical_rules", "applied", {
        "file": file_path,
        "rule_count": len(rules),
        "sources": [r["source"] for r in rules]
    })

    return Response.allow(f"[Rules] {message}")


@graceful_main("hierarchical_rules")
def main():
    try:
        ctx = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    result = check_hierarchical_rules(ctx)
    if result:
        print(json.dumps(result))

    sys.exit(0)


if __name__ == "__main__":
    main()

#!/home/jonglaser/.claude/data/venv/bin/python3
"""
Tool Analytics - Unified tool tracking, output metrics, failure detection, and build analysis.

Consolidates:
- tool_success_tracker: Track tool failures and suggest alternatives
- output_metrics: Token tracking and output size monitoring
- build_analyzer: Parse build errors and provide fix suggestions

All share token estimation logic and PostToolUse context processing.
"""
import heapq
import re
import time
from datetime import datetime
from pathlib import Path

from hooks.hook_utils import (
    log_event,
    safe_load_json,
    safe_save_json,
    get_session_id,
    read_session_state,
    write_session_state,
    estimate_tokens,
    get_content_size,
)
from hooks.hook_sdk import PostToolUseContext, Response
from hooks.config import Thresholds, FilePatterns, Timeouts, Limits, TRACKER_DIR, ToolAnalytics, Build

# =============================================================================
# Shared Configuration
# =============================================================================

CHARS_PER_TOKEN = Thresholds.CHARS_PER_TOKEN
OUTPUT_WARNING_THRESHOLD = Thresholds.OUTPUT_WARNING
OUTPUT_CRITICAL_THRESHOLD = Thresholds.OUTPUT_CRITICAL
DAILY_WARNING_THRESHOLD = Thresholds.DAILY_TOKEN_WARNING
LARGE_OUTPUT_TOOLS = FilePatterns.LARGE_OUTPUT_TOOLS
FAILURE_THRESHOLD = Thresholds.TOOL_FAILURE_THRESHOLD
TOOL_TRACKER_MAX_AGE = Timeouts.TOOL_TRACKER_MAX_AGE
STATE_NAMESPACE = "tool_tracker"

# =============================================================================
# Tool Success Tracker
# =============================================================================

# Error patterns and tool alternatives from centralized config
def get_error_patterns():
    """Get compiled error patterns for matching."""
    return ToolAnalytics.get_error_patterns()

TOOL_ALTERNATIVES = ToolAnalytics.TOOL_ALTERNATIVES or {
    "Grep": "Consider Task(subagent_type=Explore) for complex searches",
    "Glob": "Try smart-find.sh with fd for faster, .gitignore-aware search",
    "Read": "For large files, use smart-view.sh",
    "Edit": "If edits keep failing, re-read file or check for concurrent modifications",
    "Bash": "For build/test commands, pipe through compress-*.sh scripts",
}


def load_tracker_state(session_id: str) -> dict:
    """Load failure history state for session."""
    now = time.time()
    default = {"failures": {}, "last_update": now}
    state = read_session_state(STATE_NAMESPACE, session_id, default)
    if now - state.get("last_update", 0) > TOOL_TRACKER_MAX_AGE:
        return default
    return state


def save_tracker_state(session_id: str, state: dict):
    """Save failure history state."""
    state["last_update"] = time.time()
    write_session_state(STATE_NAMESPACE, state, session_id)


def extract_error_info(tool_result) -> tuple[bool, str]:
    """Extract error status and message from tool result."""
    if isinstance(tool_result, str):
        return False, tool_result[:500]
    if not isinstance(tool_result, dict):
        return False, str(tool_result)[:500] if tool_result else ""

    is_error = tool_result.get("is_error", False)
    error_msg = ""
    content = tool_result.get("content", "")
    if isinstance(content, str):
        error_msg = content
    elif isinstance(content, list):
        for item in content:
            if isinstance(item, dict):
                text = item.get("text", "")
                if text:
                    error_msg += text + "\n"

    return is_error, error_msg[:500]


def match_error_pattern(error_msg: str) -> dict | None:
    """Match error message against pre-compiled patterns."""
    for compiled, info in get_error_patterns():
        if compiled.search(error_msg):
            return info
    return None


def track_success(ctx: PostToolUseContext) -> list[str]:
    """Track tool success/failure. Returns list of messages."""
    tool_name = ctx.tool_name
    tool_result = ctx.tool_result.raw
    session_id = get_session_id(ctx.raw)

    if not tool_name:
        return []

    state = load_tracker_state(session_id)

    if tool_name not in state["failures"]:
        state["failures"][tool_name] = {
            "count": 0,
            "recent_errors": [],
            "last_success": time.time()
        }

    is_error, error_msg = extract_error_info(tool_result)
    messages = []

    if is_error or (error_msg and match_error_pattern(error_msg)):
        tool_failures = state["failures"][tool_name]
        tool_failures["count"] += 1
        tool_failures["recent_errors"].append({
            "msg": error_msg[:200],
            "time": time.time()
        })
        tool_failures["recent_errors"] = tool_failures["recent_errors"][-10:]

        pattern_match = match_error_pattern(error_msg)
        if pattern_match:
            messages.append(f"[Tool Tracker] {tool_name} error detected")
            messages.append(f"  Suggestion: {pattern_match['suggestion']}")
            log_event("tool_analytics", "error_pattern_matched", {"tool": tool_name, "action": pattern_match["action"]})
        elif tool_failures["count"] >= FAILURE_THRESHOLD:
            messages.append(f"[Tool Tracker] {tool_name} has failed {tool_failures['count']} times this session")
            if tool_name in TOOL_ALTERNATIVES:
                messages.append(f"  Alternative: {TOOL_ALTERNATIVES[tool_name]}")
            log_event("tool_analytics", "repeated_failures", {"tool": tool_name, "count": tool_failures["count"]})
    else:
        if tool_name in state["failures"]:
            state["failures"][tool_name]["count"] = 0
            state["failures"][tool_name]["last_success"] = time.time()

    save_tracker_state(session_id, state)
    return messages


# =============================================================================
# Token Tracker & Output Size Monitor
# =============================================================================

# Use TTLCache with centralized config (cache invalidates on date change check anyway)
from cachetools import TTLCache
_daily_stats_cache: TTLCache = TTLCache(maxsize=Limits.DAILY_STATS_CACHE_MAXSIZE, ttl=Timeouts.DAILY_STATS_CACHE_TTL)
_DAILY_STATS_KEY = "daily_stats"


def get_daily_log_path() -> Path:
    """Get path to today's token log."""
    today = datetime.now().strftime("%Y-%m-%d")
    return TRACKER_DIR / f"tokens-{today}.json"


def load_daily_stats() -> dict:
    """Load today's statistics with caching."""
    today = datetime.now().strftime("%Y-%m-%d")

    # Check cache - but invalidate if date changed
    if _DAILY_STATS_KEY in _daily_stats_cache:
        cached = _daily_stats_cache[_DAILY_STATS_KEY]
        if cached.get("date") == today:
            return cached

    log_path = get_daily_log_path()
    default = {
        "date": today,
        "total_tokens": 0,
        "tool_calls": 0,
        "by_tool": {},
        "sessions": 0,
    }
    data = safe_load_json(log_path, default)

    _daily_stats_cache[_DAILY_STATS_KEY] = data
    return data


def save_daily_stats(stats: dict, force: bool = False):
    """Save today's statistics with batching."""
    _daily_stats_cache[_DAILY_STATS_KEY] = stats

    if force or stats.get("tool_calls", 0) % Thresholds.STATS_FLUSH_INTERVAL == 0:
        TRACKER_DIR.mkdir(parents=True, exist_ok=True)
        log_path = get_daily_log_path()
        safe_save_json(log_path, stats)


def track_tokens(ctx: PostToolUseContext) -> list[str]:
    """Track token usage. Returns list of messages if warning threshold reached."""
    tool_name = ctx.tool_name or "unknown"
    tool_input = ctx.tool_input.raw
    tool_result = ctx.tool_result.raw

    input_tokens = estimate_tokens(tool_input)
    output_tokens = estimate_tokens(tool_result)
    total_tokens = input_tokens + output_tokens

    stats = load_daily_stats()
    stats["total_tokens"] += total_tokens
    stats["tool_calls"] += 1
    stats["by_tool"][tool_name] = stats["by_tool"].get(tool_name, 0) + total_tokens
    save_daily_stats(stats)

    messages = []
    if stats["total_tokens"] >= DAILY_WARNING_THRESHOLD:
        if stats["tool_calls"] % 50 == 0:
            messages.append(f"[Token Tracker] Daily usage: ~{stats['total_tokens']:,} tokens")
            top_tools = heapq.nlargest(3, stats["by_tool"].items(), key=lambda x: x[1])
            if top_tools:
                tools_str = ", ".join(f"{t}: {c:,}" for t, c in top_tools)
                messages.append(f"  Top tools: {tools_str}")

    return messages


def check_output_size(ctx: PostToolUseContext) -> list[str]:
    """Check output size. Returns list of messages if too large."""
    tool_name = ctx.tool_name
    tool_result = ctx.tool_result.raw

    output_size = get_content_size(tool_result)
    if output_size == 0:
        return []

    estimated_tokens = estimate_tokens(tool_result)

    warning_threshold = OUTPUT_WARNING_THRESHOLD
    critical_threshold = OUTPUT_CRITICAL_THRESHOLD
    if tool_name in LARGE_OUTPUT_TOOLS:
        warning_threshold *= 3
        critical_threshold *= 3

    messages = []

    if output_size >= critical_threshold:
        messages.append(f"[Output Monitor] Large output from {tool_name}: ~{estimated_tokens:,} tokens ({output_size:,} chars)")
        messages.append("  Consider using compression scripts or limiting output.")
        if tool_name == "Bash":
            messages.append("  Tip: Pipe to head, use compress-*.sh scripts, or add output limits")
        elif tool_name == "Grep":
            messages.append("  Tip: Use head_limit parameter or offload-grep.sh")
        elif tool_name == "Read":
            messages.append("  Tip: Use smart-view.sh for large files")
    elif output_size >= warning_threshold:
        messages.append(f"[Output Monitor] {tool_name} output: ~{estimated_tokens:,} tokens")

    return messages


# =============================================================================
# Build Analyzer (consolidated from build_analyzer.py)
# =============================================================================

# Import patterns from centralized config
BUILD_COMMANDS = Build.get_build_commands()
BUILD_ERROR_PATTERNS = Build.get_error_patterns()
BUILD_FIX_SUGGESTIONS = Build.FIX_SUGGESTIONS


def is_build_command(command: str) -> bool:
    """Check if command is a build-related command."""
    for pattern in BUILD_COMMANDS:
        if pattern.search(command):
            return True
    return False


def detect_build_tool(command: str, output: str) -> str:
    """Detect which build tool was used."""
    cmd_lower = command.lower()

    if 'cargo' in cmd_lower or 'rustc' in cmd_lower:
        return 'rust'
    if 'npm' in cmd_lower or 'yarn' in cmd_lower or 'pnpm' in cmd_lower:
        return 'npm'
    if 'tsc' in cmd_lower or 'typescript' in output.lower():
        return 'typescript'
    if 'go ' in cmd_lower:
        return 'go'
    if 'python' in cmd_lower or 'pip' in cmd_lower:
        return 'python'
    if any(x in cmd_lower for x in ['gcc', 'g++', 'clang', 'make', 'cmake', 'ninja']):
        return 'gcc_clang'
    if 'gradle' in cmd_lower or 'mvn' in cmd_lower:
        return 'java'

    # Detect from output
    if 'error[E' in output:
        return 'rust'
    if 'error TS' in output:
        return 'typescript'
    if '.go:' in output and 'undefined' in output:
        return 'go'

    return 'make'  # Default fallback


def extract_build_errors(output: str, tool: str) -> list:
    """Extract error messages from build output."""
    errors = []
    patterns = BUILD_ERROR_PATTERNS.get(tool, BUILD_ERROR_PATTERNS.get('make', []))

    for line in output.split('\n'):
        line = line.strip()
        if not line:
            continue

        for pattern, category in patterns:
            match = pattern.search(line)
            if match:
                errors.append({
                    'line': line[:200],
                    'match': match.group(0)[:150],
                })
                break

        if len(errors) < 20 and 'error' in line.lower() and line not in [e['line'] for e in errors]:
            if not any(skip in line.lower() for skip in ['warning', 'note:', 'help:']):
                errors.append({'line': line[:200], 'match': None})

    return errors[:15]


def get_build_suggestions(errors: list, output: str) -> list:
    """Get fix suggestions based on errors."""
    suggestions = set()
    combined = output + ' '.join(e.get('match') or e.get('line', '') for e in errors)

    for pattern, suggestion in BUILD_FIX_SUGGESTIONS.items():
        if pattern.lower() in combined.lower():
            suggestions.add(suggestion)

    return list(suggestions)[:5]


def count_errors_warnings(output: str) -> tuple:
    """Count errors and warnings in output."""
    error_count = len(re.findall(r'\berror[:\[]', output, re.IGNORECASE))
    warning_count = len(re.findall(r'\bwarning[:\[]', output, re.IGNORECASE))

    # Also check for "X errors" pattern
    match = re.search(r'(\d+)\s+error', output, re.IGNORECASE)
    if match:
        error_count = max(error_count, int(match.group(1)))

    return error_count, warning_count


def analyze_build(ctx: PostToolUseContext) -> list[str]:
    """Analyze build output and return summary messages."""
    if ctx.tool_name != 'Bash':
        return []

    command = ctx.tool_input.command
    output = ctx.tool_result.output

    # Get exit code
    exit_code = ctx.tool_result.exit_code
    if exit_code is None:
        # Try to detect from output
        if 'error' in output.lower() and ('make: ***' in output or 'FAILED' in output):
            exit_code = 1
        else:
            exit_code = 0

    if exit_code == 0:
        return []

    if not is_build_command(command):
        return []

    # Analyze errors
    tool = detect_build_tool(command, output)
    errors = extract_build_errors(output, tool)
    suggestions = get_build_suggestions(errors, output)
    error_count, warning_count = count_errors_warnings(output)

    if not errors and error_count == 0:
        return []

    # Format summary
    messages = [f"[Build: {tool}] {max(error_count, len(errors))} errors, {warning_count} warnings"]

    if errors and errors[0].get('line'):
        messages.append(f"  First: {errors[0]['line'][:80]}")

    if suggestions:
        messages.append(f"  Fix: {suggestions[0]}")

    return messages


# =============================================================================
# Combined Handler
# =============================================================================

def track_tool_analytics(raw: dict) -> dict | None:
    """Combined handler for tool success tracking, token tracking, output monitoring, and build analysis."""
    ctx = PostToolUseContext(raw)
    all_messages = []

    # Track tool success/failure
    success_messages = track_success(ctx)
    all_messages.extend(success_messages)

    # Track tokens (always runs, updates stats)
    token_messages = track_tokens(ctx)
    all_messages.extend(token_messages)

    # Check output size
    size_messages = check_output_size(ctx)
    all_messages.extend(size_messages)

    # Analyze build failures (for Bash commands)
    build_messages = analyze_build(ctx)
    all_messages.extend(build_messages)

    if all_messages:
        return Response.message(" | ".join(all_messages[:3]), event="PostToolUse")

    return None

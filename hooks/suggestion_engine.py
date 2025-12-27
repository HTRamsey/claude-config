#!/home/jonglaser/.claude/data/venv/bin/python3
"""
Suggestion Engine - Unified suggestion system for Claude Code.

Consolidates:
- skill_suggester: Suggests creator skills for config files
- suggest_subagent: Suggests agent delegation for exploration
- suggest_tool_optimization: Suggests better tool alternatives
- agent_chaining: Suggests follow-up specialists after Task

All handlers share state, patterns, and reduce process spawns.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from hook_utils import graceful_main, log_event

# ============================================================================
# Shared State
# ============================================================================

DATA_DIR = Path.home() / ".claude/data"
CACHE_DIR = DATA_DIR / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
SUGGESTION_CACHE = CACHE_DIR / "suggestion-engine-cache.json"

_state = None

def get_state() -> dict:
    """Load or initialize shared suggestion state."""
    global _state
    if _state is not None:
        return _state
    try:
        if SUGGESTION_CACHE.exists():
            with open(SUGGESTION_CACHE) as f:
                _state = json.load(f)
        else:
            _state = {}
    except Exception:
        _state = {}
    return _state

def save_state():
    """Persist state to disk."""
    if _state is not None:
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            with open(SUGGESTION_CACHE, "w") as f:
                json.dump(_state, f)
        except Exception:
            pass

# ============================================================================
# Skill Suggester (PreToolUse: Write, Edit)
# ============================================================================

SKILL_SUGGESTIONS = [
    {"pattern": r"\.claude/hooks/.*\.py$", "skill": "hook-creator", "type": "hook"},
    {"pattern": r"\.claude/agents/.*\.md$", "skill": "agent-creator", "type": "agent"},
    {"pattern": r"\.claude/commands/.*\.md$", "skill": "command-creator", "type": "command"},
    {"pattern": r"\.claude/skills/.*/SKILL\.md$", "skill": "skill-creator", "type": "skill"},
]

def suggest_skill(ctx: dict) -> dict | None:
    """Suggest creator skills when writing config files."""
    tool_name = ctx.get("tool_name", "")
    if tool_name not in ("Write", "Edit"):
        return None

    file_path = ctx.get("tool_input", {}).get("file_path", "")
    if not file_path:
        return None

    state = get_state()
    suggested = set(state.get("skills_suggested", []))

    for rule in SKILL_SUGGESTIONS:
        if re.search(rule["pattern"], file_path):
            cache_key = f"{rule['skill']}:{Path(file_path).name}"
            if cache_key in suggested:
                return None

            suggested.add(cache_key)
            state["skills_suggested"] = list(suggested)
            save_state()

            return {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "allow",
                    "permissionDecisionReason": (
                        f"Creating {rule['type']} file. "
                        f"Consider using the `{rule['skill']}` skill for correct format and patterns. "
                        f"Load with: Skill(skill=\"{rule['skill']}\")"
                    )
                }
            }
    return None

# ============================================================================
# Subagent Suggester (PreToolUse: Grep, Glob, Read)
# ============================================================================

AGENT_RECOMMENDATIONS = {
    "exploration": ("Explore", "Haiku-powered codebase exploration"),
    "lookup": ("quick-lookup", "Single fact retrieval (Haiku, 10x cheaper)"),
}

def suggest_subagent(ctx: dict) -> dict | None:
    """Suggest agent delegation for exploration patterns."""
    tool_name = ctx.get("tool_name", "")
    tool_input = ctx.get("tool_input", {})

    if tool_name not in ("Grep", "Glob", "Read"):
        return None

    state = get_state()
    pattern = tool_input.get("pattern", "")
    path = tool_input.get("path", tool_input.get("file_path", ""))

    # Track consecutive searches
    if tool_name in ("Grep", "Glob"):
        state["consecutive_searches"] = state.get("consecutive_searches", 0) + 1
        recent = state.get("recent_patterns", [])
        recent.append(pattern)
        state["recent_patterns"] = recent[-5:]
    else:
        if state.get("consecutive_searches", 0) > 0:
            state["consecutive_searches"] = 0

    save_state()

    # Rule 1: Multiple consecutive searches
    if state.get("consecutive_searches", 0) >= 3:
        return _subagent_suggestion(
            "exploration",
            f"Multiple searches detected ({state['consecutive_searches']}). "
            "Consider Task(Explore) to search more efficiently."
        )

    # Rule 2: Broad glob patterns
    if tool_name == "Glob" and pattern:
        if "**" in pattern or pattern.count("*") >= 2:
            if not path or path in (".", "./", "/"):
                return _subagent_suggestion(
                    "exploration",
                    "Broad glob pattern. Consider Task(Explore) for codebase-wide search."
                )

    # Rule 3: Generic grep without specific path
    if tool_name == "Grep":
        if not path or path in (".", "./"):
            if len(pattern) < 15 and not pattern.startswith("^"):
                return _subagent_suggestion(
                    "exploration",
                    "Exploratory grep. Consider Task(Explore) for better context management."
                )

    # Rule 4: Reading many files
    if tool_name == "Read":
        reads = state.get("recent_reads", 0) + 1
        state["recent_reads"] = reads
        save_state()
        if reads >= 5:
            return _subagent_suggestion(
                "exploration",
                f"Reading multiple files ({reads}). Consider Task(Explore) to offload exploration."
            )

    return None

def _subagent_suggestion(agent_type: str, reason: str) -> dict:
    agent_name, agent_desc = AGENT_RECOMMENDATIONS.get(agent_type, ("Explore", ""))
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "permissionDecisionReason": (
                f"[Subagent Suggestion] {reason}\n"
                f"  Recommended: Task(subagent_type='{agent_name}') - {agent_desc}"
            )
        }
    }

# ============================================================================
# Tool Optimization (PreToolUse: Bash, Grep, Read)
# ============================================================================

BASH_ALTERNATIVES = {
    r"^grep\s": ("offload-grep.sh", "97% token savings"),
    r"^rg\s": ("offload-grep.sh", "97% token savings"),
    r"^find\s": ("offload-find.sh", "95% token savings"),
    r"^git\s+diff": ("smart-diff.sh", "uses delta, 99% savings on large diffs"),
    r"^cat\s.*\.(log|txt)": ("compress-logs.sh", "errors/warnings only"),
    r"^npm\s+(test|run\s+test)": ("compress.sh --type tests", "pipe output"),
    r"^pytest": ("compress.sh --type tests", "pipe output"),
    r"^make\b": ("compress.sh --type build", "pipe for errors only"),
    r"^cmake\b": ("compress.sh --type build", "pipe for errors only"),
    r"^ls\s+(-la|-l|-a)": ("smart-ls.sh", "uses eza, 87% smaller output"),
    r"^ls\s*$": ("smart-ls.sh", "uses eza, 87% smaller output"),
    r"^tree\s": ("smart-tree.sh", "uses eza --tree, respects .gitignore"),
    r"^sed\s": ("smart-replace.sh", "uses sd, simpler syntax"),
    r"^find\s.*-name": ("smart-find.sh", "uses fd, 10x faster, respects .gitignore"),
    r"^cat\s": ("smart/smart-view.sh", "unified viewer with syntax highlighting"),
    r"^head\s": ("smart/smart-view.sh", "unified viewer with line range"),
    r"^tail\s": ("smart/smart-view.sh", "unified viewer with line range"),
    r"^du\s": ("smart-du.sh", "uses dust, compact visual output"),
    r"^diff\s": ("smart-difft.sh", "uses difftastic, structural diff"),
    r"^git\s+blame": ("smart-blame.sh", "filters formatting commits, adds context"),
    r"^(cat|less).*\.json\s*\|\s*jq": ("smart-json.sh", "simpler field extraction syntax"),
    r"^grep.*def\s": ("smart-ast.sh", "uses ast-grep, finds function definitions structurally"),
    r"^grep.*class\s": ("smart-ast.sh", "uses ast-grep, finds class definitions structurally"),
    r"^grep.*function\s": ("smart-ast.sh", "uses ast-grep, finds function definitions structurally"),
    r"^grep.*import\s": ("smart-ast.sh", "uses ast-grep, finds imports structurally"),
}

def suggest_optimization(ctx: dict) -> dict | None:
    """Suggest better tool alternatives."""
    tool_name = ctx.get("tool_name", "")
    tool_input = ctx.get("tool_input", {})

    suggestion = None

    if tool_name == "Bash":
        command = tool_input.get("command", "").strip()
        for pattern, (alt, reason) in BASH_ALTERNATIVES.items():
            if re.search(pattern, command, re.IGNORECASE):
                suggestion = f"Consider ~/.claude/scripts/{alt} ({reason})"
                break

    elif tool_name == "Grep":
        output_mode = tool_input.get("output_mode", "files_with_matches")
        if output_mode == "content" and not tool_input.get("head_limit"):
            suggestion = "Add head_limit to Grep to reduce token usage"

    elif tool_name == "Read":
        file_path = tool_input.get("file_path", "")
        try:
            if file_path and Path(file_path).exists():
                size = Path(file_path).stat().st_size
                if size > 50000:
                    suggestion = "Large file - consider smart-view.sh"
        except Exception:
            pass

    if suggestion:
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "permissionDecisionReason": f"[Optimization] {suggestion}"
            }
        }

    return None

# ============================================================================
# Agent Chaining (PostToolUse: Task)
# ============================================================================

CHAIN_RULES = [
    {
        "patterns": [
            r"(?i)(sql injection|xss|csrf|command injection|path traversal)",
            r"(?i)(hardcoded (credential|secret|password|api.?key))",
            r"(?i)(authentication|authorization).*(missing|bypass|vulnerable)",
            r"(?i)(insecure|vulnerable).*(crypto|random|hash)",
            r"(?i)🔴.*security",
        ],
        "agent": "code-reviewer",
        "reason": "Security vulnerability detected - deep security analysis recommended",
    },
    {
        "patterns": [
            r"(?i)(n\+1|n \+ 1).*(query|queries)",
            r"(?i)(memory leak|unbounded|allocation in (hot|loop))",
            r"(?i)O\(n[²2]\)|O\(n\^2\)",
            r"(?i)(performance|slow).*(critical|severe|significant)",
            r"(?i)🟡.*performance",
        ],
        "agent": "code-reviewer",
        "reason": "Performance issue detected - code review with performance focus recommended",
    },
    {
        "patterns": [
            r"(?i)(accessibility|a11y|wcag|aria).*(missing|issue|violation)",
            r"(?i)(screen reader|keyboard).*(navigation|focus|trap)",
            r"(?i)\.(jsx|tsx|vue|svelte|qml):\d+",
        ],
        "agent": "code-reviewer",
        "reason": "UI code or accessibility issue - code review with accessibility focus recommended",
    },
    {
        "patterns": [
            r"(?i)(no test|missing test|untested|test coverage).*(low|none|missing)",
            r"(?i)(edge case|boundary|error handling).*(not|missing|untested)",
        ],
        "agent": "test-generator",
        "reason": "Test gaps detected - test generation recommended",
    },
    {
        "patterns": [
            r"(?i)(unused|dead|orphan).*(function|class|import|variable|code)",
            r"(?i)(deprecated|obsolete).*(still|found|exists)",
        ],
        "agent": "code-reviewer",
        "reason": "Potential dead code - code review for cleanup recommended",
    },
]

CHAINABLE_AGENTS = {"code-reviewer", "Explore", "error-explainer", "quick-lookup"}

def suggest_chain(ctx: dict) -> dict | None:
    """Suggest follow-up specialists based on Task output."""
    tool_name = ctx.get("tool_name", "")
    tool_input = ctx.get("tool_input", {})
    tool_output = ctx.get("tool_result", ctx.get("tool_response", {}))

    if tool_name != "Task":
        return None

    source_agent = tool_input.get("subagent_type", "")
    if source_agent not in CHAINABLE_AGENTS:
        return None

    output = ""
    if isinstance(tool_output, dict):
        output = tool_output.get("output", "") or tool_output.get("content", "")
    elif isinstance(tool_output, str):
        output = tool_output

    if not output:
        return None

    recommendations = []
    seen_agents = set()

    for rule in CHAIN_RULES:
        for pattern in rule["patterns"]:
            if re.search(pattern, output):
                agent = rule["agent"]
                if agent not in seen_agents and agent != source_agent:
                    recommendations.append({"agent": agent, "reason": rule["reason"]})
                    seen_agents.add(agent)
                break

    if recommendations:
        msg_lines = [f"[Agent Chaining] Based on {source_agent} findings:"]
        for rec in recommendations[:2]:
            msg_lines.append(f"  → Task(subagent_type='{rec['agent']}') - {rec['reason']}")
        msg_lines.append("  Use orchestrator for comprehensive multi-agent review.")

        return {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "message": "\n".join(msg_lines)
            }
        }

    return None

# ============================================================================
# Main (standalone execution)
# ============================================================================

@graceful_main("suggestion_engine")
def main():
    try:
        ctx = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    event = ctx.get("event", "")
    tool_name = ctx.get("tool_name", "")

    result = None

    if event == "PreToolUse":
        if tool_name in ("Write", "Edit"):
            result = suggest_skill(ctx)
        elif tool_name in ("Grep", "Glob", "Read"):
            result = suggest_subagent(ctx) or suggest_optimization(ctx)
        elif tool_name == "Bash":
            result = suggest_optimization(ctx)
    elif event == "PostToolUse":
        if tool_name == "Task":
            result = suggest_chain(ctx)

    if result:
        print(json.dumps(result))

    sys.exit(0)


if __name__ == "__main__":
    main()

#!/home/jonglaser/.claude/venv/bin/python3
"""
Suggest Subagent Hook - Promotes subagent usage for exploration patterns.

PreToolUse hook for Grep|Glob|Read that detects patterns better suited
for subagent delegation and suggests the appropriate agent.
"""
import json
import sys
import os
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


# Track consecutive exploration calls in this session
STATE_FILE = f"/tmp/claude-exploration-{os.getuid()}.json"

# Patterns that suggest exploration (should use subagent)
EXPLORATION_INDICATORS = [
    # Search patterns
    "where", "find", "search", "look for", "locate",
    # Understanding patterns
    "how does", "how is", "what is", "understand", "explain",
    # Review patterns
    "review", "audit", "check", "analyze",
    # Multi-file patterns
    "all files", "across", "throughout", "codebase",
]

# Agent recommendations by pattern type
AGENT_RECOMMENDATIONS = {
    "exploration": ("Explore", "Haiku-powered codebase exploration"),
    "lookup": ("quick-lookup", "Single fact retrieval (Haiku, 10x cheaper)"),
    "review": ("code-reviewer", "Thorough code review"),
    "error": ("error-explainer", "Error analysis (Haiku)"),
}


def load_state():
    try:
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"consecutive_searches": 0, "recent_patterns": []}


def save_state(state):
    try:
        with open(STATE_FILE, 'w') as f:
            json.dump(state, f)
    except IOError:
        pass


def detect_exploration_intent(tool_name: str, tool_input: dict, state: dict) -> tuple:
    """
    Detect if the current operation looks like exploration.
    Returns (should_suggest, agent_type, reason)
    """
    pattern = tool_input.get("pattern", "")
    path = tool_input.get("path", tool_input.get("file_path", ""))

    # Track consecutive search operations
    if tool_name in ("Grep", "Glob"):
        state["consecutive_searches"] = state.get("consecutive_searches", 0) + 1
        state["recent_patterns"].append(pattern)
        # Keep only last 5
        state["recent_patterns"] = state["recent_patterns"][-5:]
    else:
        # Read resets the counter (they're executing on results)
        if state.get("consecutive_searches", 0) > 0:
            state["consecutive_searches"] = 0

    # Rule 1: Multiple consecutive searches suggest exploration
    if state.get("consecutive_searches", 0) >= 3:
        return (True, "exploration",
                f"Multiple searches detected ({state['consecutive_searches']}). "
                "Consider Task(Explore) to search more efficiently.")

    # Rule 2: Broad glob patterns suggest exploration
    if tool_name == "Glob":
        if pattern and ("**" in pattern or pattern.count("*") >= 2):
            if not path or path in (".", "./", "/"):
                return (True, "exploration",
                        "Broad glob pattern. Consider Task(Explore) for codebase-wide search.")

    # Rule 3: Generic grep patterns without specific path
    if tool_name == "Grep":
        if not path or path in (".", "./"):
            # Check if pattern looks exploratory (not a specific symbol lookup)
            if len(pattern) < 15 and not pattern.startswith("^"):
                return (True, "exploration",
                        "Exploratory grep. Consider Task(Explore) for better context management.")

    # Rule 4: Reading many files in sequence (detected via state)
    if tool_name == "Read":
        reads = state.get("recent_reads", 0) + 1
        state["recent_reads"] = reads
        if reads >= 5:
            return (True, "exploration",
                    f"Reading multiple files ({reads}). Consider Task(Explore) to offload exploration.")

    return (False, None, None)


@graceful_main("suggest_subagent")
def main():
    try:
        ctx = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = ctx.get("tool_name", "")
    tool_input = ctx.get("tool_input", {})

    # Only check exploration tools
    if tool_name not in ("Grep", "Glob", "Read"):
        sys.exit(0)

    state = load_state()
    should_suggest, agent_type, reason = detect_exploration_intent(tool_name, tool_input, state)
    save_state(state)

    if should_suggest and agent_type:
        agent_name, agent_desc = AGENT_RECOMMENDATIONS.get(agent_type, ("Explore", ""))
        message = (
            f"[Subagent Suggestion] {reason}\n"
            f"  Recommended: Task(subagent_type='{agent_name}') - {agent_desc}\n"
            f"  This offloads exploration to a subagent, saving main context tokens."
        )
        result = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "permissionDecisionReason": message
            }
        }
        print(json.dumps(result))

    sys.exit(0)


if __name__ == "__main__":
    main()

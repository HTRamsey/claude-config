"""
Subagent Suggester - Suggests agent delegation for exploration patterns.

PreToolUse: Grep, Glob, Read
"""
from .shared import get_state, update_state, save_state
from hook_sdk import PreToolUseContext, Response


AGENT_RECOMMENDATIONS = {
    "exploration": ("Explore", "Haiku-powered codebase exploration"),
    "lookup": ("quick-lookup", "Single fact retrieval (Haiku, 10x cheaper)"),
}


def suggest_subagent(raw: dict) -> dict | None:
    """Suggest agent delegation for exploration patterns."""
    ctx = PreToolUseContext(raw)

    if ctx.tool_name not in ("Grep", "Glob", "Read"):
        return None

    state = get_state()
    pattern = ctx.tool_input.pattern or ""
    path = ctx.tool_input.path or ctx.tool_input.file_path or ""

    # Track consecutive searches
    if ctx.tool_name in ("Grep", "Glob"):
        consecutive = state.get("consecutive_searches", 0) + 1
        recent = state.get("recent_patterns", [])
        recent.append(pattern)
        update_state({
            "consecutive_searches": consecutive,
            "recent_patterns": recent[-5:]
        })
    else:
        if state.get("consecutive_searches", 0) > 0:
            update_state({"consecutive_searches": 0})

    save_state()
    state = get_state()  # Refresh after update

    # Rule 1: Multiple consecutive searches
    if state.get("consecutive_searches", 0) >= 3:
        return _subagent_suggestion(
            "exploration",
            f"Multiple searches detected ({state['consecutive_searches']}). "
            "Consider Task(Explore) to search more efficiently."
        )

    # Rule 2: Broad glob patterns
    if ctx.tool_name == "Glob" and pattern:
        if "**" in pattern or pattern.count("*") >= 2:
            if not path or path in (".", "./", "/"):
                return _subagent_suggestion(
                    "exploration",
                    "Broad glob pattern. Consider Task(Explore) for codebase-wide search."
                )

    # Rule 3: Generic grep without specific path
    if ctx.tool_name == "Grep":
        if not path or path in (".", "./"):
            if len(pattern) < 15 and not pattern.startswith("^"):
                return _subagent_suggestion(
                    "exploration",
                    "Exploratory grep. Consider Task(Explore) for better context management."
                )

    # Rule 4: Reading many files
    if ctx.tool_name == "Read":
        reads = state.get("recent_reads", 0) + 1
        update_state({"recent_reads": reads})
        save_state()
        if reads >= 5:
            return _subagent_suggestion(
                "exploration",
                f"Reading multiple files ({reads}). Consider Task(Explore) to offload exploration."
            )

    return None


def _subagent_suggestion(agent_type: str, reason: str) -> dict:
    agent_name, agent_desc = AGENT_RECOMMENDATIONS.get(agent_type, ("Explore", ""))
    decision_reason = (
        f"[Subagent Suggestion] {reason}\n"
        f"  Recommended: Task(subagent_type='{agent_name}') - {agent_desc}"
    )
    return Response.allow(decision_reason)

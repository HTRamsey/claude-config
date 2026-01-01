"""
Skill Suggester - Suggests creator skills for config files.

PreToolUse: Write, Edit
"""
import re
from pathlib import Path

from .shared import get_state, update_state, save_state
from hook_sdk import PreToolUseContext, Response


SKILL_SUGGESTIONS = [
    {"pattern": re.compile(r"\.claude/hooks/.*\.py$"), "skill": "hook-creator", "type": "hook"},
    {"pattern": re.compile(r"\.claude/agents/.*\.md$"), "skill": "agent-creator", "type": "agent"},
    {"pattern": re.compile(r"\.claude/commands/.*\.md$"), "skill": "command-creator", "type": "command"},
    {"pattern": re.compile(r"\.claude/skills/.*/SKILL\.md$"), "skill": "skill-creator", "type": "skill"},
]


def suggest_skill(raw: dict) -> dict | None:
    """Suggest creator skills when writing config files."""
    ctx = PreToolUseContext(raw)
    if ctx.tool_name not in ("Write", "Edit"):
        return None

    file_path = ctx.tool_input.file_path
    if not file_path:
        return None

    state = get_state()
    suggested = set(state.get("skills_suggested", []))

    for rule in SKILL_SUGGESTIONS:
        if rule["pattern"].search(file_path):
            cache_key = f"{rule['skill']}:{Path(file_path).name}"
            if cache_key in suggested:
                return None

            suggested.add(cache_key)
            update_state({"skills_suggested": list(suggested)})
            save_state()

            reason = (
                f"Creating {rule['type']} file. "
                f"Consider using the `{rule['skill']}` skill for correct format and patterns. "
                f"Load with: Skill(skill=\"{rule['skill']}\")"
            )
            return Response.allow(reason)
    return None

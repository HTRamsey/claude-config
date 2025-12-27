#!/home/jonglaser/.claude/data/venv/bin/python3
"""
Usage Tracker Hook - Tracks skill, agent, and command usage.

PreToolUse: Tracks Task (agents) and Skill tool invocations
UserPromptSubmit: Tracks slash command usage
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from hook_utils import graceful_main, record_usage

BUILTIN_COMMANDS = {
    "help", "clear", "compact", "cost", "doctor", "init", "config",
    "memory", "model", "permissions", "status", "vim", "terminal-setup",
    "bug", "diff", "login", "logout", "listen", "mcp", "resume",
    "add-dir", "pr-comments", "ide", "rename", "rewind", "tasks"
}


def track_usage(ctx: dict) -> dict | None:
    """Handler function for dispatcher. Returns None (tracking only)."""
    tool_name = ctx.get("tool_name", "")
    tool_input = ctx.get("tool_input", {})

    if tool_name == "Task":
        agent_type = tool_input.get("subagent_type", "")
        if agent_type:
            record_usage("agents", agent_type)
    elif tool_name == "Skill":
        skill_name = tool_input.get("skill", "")
        if skill_name:
            record_usage("skills", skill_name)

    user_prompt = ctx.get("user_prompt", "") or ctx.get("prompt", "")
    if user_prompt and user_prompt.strip().startswith("/"):
        parts = user_prompt.strip()[1:].split(None, 1)
        if parts and parts[0].lower() not in BUILTIN_COMMANDS:
            record_usage("commands", parts[0].lower())

    return None


@graceful_main("usage_tracker")
def main():
    try:
        ctx = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    track_usage(ctx)
    sys.exit(0)


if __name__ == "__main__":
    main()

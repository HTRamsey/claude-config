#!/home/jonglaser/.claude/data/venv/bin/python3
"""
Usage Tracker Hook - Tracks skill, agent, and command usage.

PreToolUse: Tracks Task (agents) and Skill tool invocations
UserPromptSubmit: Tracks slash command usage
"""
from hooks.hook_utils import record_usage

BUILTIN_COMMANDS = {
    "help", "clear", "compact", "cost", "doctor", "init", "config",
    "memory", "model", "permissions", "status", "vim", "terminal-setup",
    "bug", "diff", "login", "logout", "listen", "mcp", "resume",
    "add-dir", "pr-comments", "ide", "rename", "rewind", "tasks"
}


def handle(raw: dict) -> dict | None:
    """Handler function for usage tracking. Returns None (tracking only)."""
    tool_name = raw.get("tool_name", "")
    tool_input = raw.get("tool_input", {})

    if tool_name == "Task":
        agent_type = tool_input.get("subagent_type", "")
        if agent_type:
            record_usage("agents", agent_type)
    elif tool_name == "Skill":
        skill_name = tool_input.get("skill", "")
        if skill_name:
            record_usage("skills", skill_name)

    user_prompt = raw.get("user_prompt", "") or raw.get("prompt", "")
    if user_prompt and user_prompt.strip().startswith("/"):
        parts = user_prompt.strip()[1:].split(None, 1)
        if parts and parts[0].lower() not in BUILTIN_COMMANDS:
            record_usage("commands", parts[0].lower())

    return None

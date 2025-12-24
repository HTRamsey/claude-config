#!/usr/bin/env python3
"""
Usage Tracker Hook - Tracks skill, agent, and command usage.

PreToolUse: Tracks Task (agents) and Skill tool invocations
UserPromptSubmit: Tracks slash command usage

Stores usage data in ~/.claude/data/usage-stats.json
"""
import json
import sys
from datetime import datetime, date
from pathlib import Path

DATA_DIR = Path.home() / ".claude" / "data"
USAGE_FILE = DATA_DIR / "usage-stats.json"

BUILTIN_COMMANDS = {
    "help", "clear", "compact", "cost", "doctor", "init", "config",
    "memory", "model", "permissions", "status", "vim", "terminal-setup",
    "bug", "diff", "login", "logout", "listen", "mcp", "resume",
    "add-dir", "pr-comments", "ide", "rename", "rewind", "tasks"
}

def load_usage():
    try:
        if USAGE_FILE.exists():
            with open(USAGE_FILE) as f:
                return json.load(f)
    except (json.JSONDecodeError, IOError):
        pass
    return {"agents": {}, "skills": {}, "commands": {}, "daily": {}, "first_seen": datetime.now().isoformat()}

def save_usage(data):
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        data["last_updated"] = datetime.now().isoformat()
        with open(USAGE_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except IOError:
        pass

def increment_usage(data, category, name):
    if category not in data:
        data[category] = {}
    if name not in data[category]:
        data[category][name] = {"count": 0, "first_used": datetime.now().isoformat(), "last_used": None, "daily_counts": {}}
    data[category][name]["count"] += 1
    data[category][name]["last_used"] = datetime.now().isoformat()
    today = date.today().isoformat()
    daily = data[category][name].get("daily_counts", {})
    daily[today] = daily.get(today, 0) + 1
    if len(daily) > 30:
        for old in sorted(daily.keys())[:-30]:
            del daily[old]
    data[category][name]["daily_counts"] = daily
    if "daily" not in data:
        data["daily"] = {}
    if today not in data["daily"]:
        data["daily"][today] = {"agents": 0, "skills": 0, "commands": 0}
    data["daily"][today][category] = data["daily"][today].get(category, 0) + 1

def main():
    try:
        ctx = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    usage = load_usage()
    tracked = False

    tool_name = ctx.get("tool_name", "")
    tool_input = ctx.get("tool_input", {})

    if tool_name == "Task":
        agent_type = tool_input.get("subagent_type", "")
        if agent_type:
            increment_usage(usage, "agents", agent_type)
            tracked = True
    elif tool_name == "Skill":
        skill_name = tool_input.get("skill", "")
        if skill_name:
            increment_usage(usage, "skills", skill_name)
            tracked = True

    user_prompt = ctx.get("user_prompt", "") or ctx.get("prompt", "")
    if user_prompt and user_prompt.strip().startswith("/"):
        parts = user_prompt.strip()[1:].split(None, 1)
        if parts and parts[0].lower() not in BUILTIN_COMMANDS:
            increment_usage(usage, "commands", parts[0].lower())
            tracked = True

    if tracked:
        save_usage(usage)
    sys.exit(0)

if __name__ == "__main__":
    main()

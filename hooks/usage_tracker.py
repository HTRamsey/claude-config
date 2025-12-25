#!/home/jonglaser/.claude/venv/bin/python3
"""
Usage Tracker Hook - Tracks skill, agent, and command usage.

PreToolUse: Tracks Task (agents) and Skill tool invocations
UserPromptSubmit: Tracks slash command usage

Uses state_manager for centralized state handling.
"""
import json
import sys
from datetime import datetime, date
from pathlib import Path

# Import shared utilities
sys.path.insert(0, str(Path(__file__).parent))
from hook_utils import graceful_main

try:
    from state_manager import get_state_manager
    HAS_STATE_MANAGER = True
except ImportError:
    HAS_STATE_MANAGER = False

# Fallback for when state_manager not available
DATA_DIR = Path.home() / ".claude" / "data"
USAGE_FILE = DATA_DIR / "usage-stats.json"

BUILTIN_COMMANDS = {
    "help", "clear", "compact", "cost", "doctor", "init", "config",
    "memory", "model", "permissions", "status", "vim", "terminal-setup",
    "bug", "diff", "login", "logout", "listen", "mcp", "resume",
    "add-dir", "pr-comments", "ide", "rename", "rewind", "tasks"
}


def _load_usage_fallback():
    """Fallback loader when state_manager unavailable."""
    try:
        if USAGE_FILE.exists():
            with open(USAGE_FILE) as f:
                return json.load(f)
    except (json.JSONDecodeError, IOError):
        pass
    return {"agents": {}, "skills": {}, "commands": {}, "daily": {}, "first_seen": datetime.now().isoformat()}


def _save_usage_fallback(data):
    """Fallback saver when state_manager unavailable."""
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        data["last_updated"] = datetime.now().isoformat()
        with open(USAGE_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except IOError:
        pass


def increment_usage(data, category, name):
    """Increment usage counter for a category/name."""
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


def track_usage(ctx: dict) -> dict | None:
    """Handler function for dispatcher. Returns None (tracking only, no output)."""
    tracked_items = []

    tool_name = ctx.get("tool_name", "")
    tool_input = ctx.get("tool_input", {})

    if tool_name == "Task":
        agent_type = tool_input.get("subagent_type", "")
        if agent_type:
            tracked_items.append(("agents", agent_type))
    elif tool_name == "Skill":
        skill_name = tool_input.get("skill", "")
        if skill_name:
            tracked_items.append(("skills", skill_name))

    user_prompt = ctx.get("user_prompt", "") or ctx.get("prompt", "")
    if user_prompt and user_prompt.strip().startswith("/"):
        parts = user_prompt.strip()[1:].split(None, 1)
        if parts and parts[0].lower() not in BUILTIN_COMMANDS:
            tracked_items.append(("commands", parts[0].lower()))

    if not tracked_items:
        return None

    # Use state_manager if available
    if HAS_STATE_MANAGER:
        sm = get_state_manager()
        for category, name in tracked_items:
            sm.record_usage(category, name)
    else:
        # Fallback to direct file access
        usage = _load_usage_fallback()
        for category, name in tracked_items:
            increment_usage(usage, category, name)
        _save_usage_fallback(usage)

    return None  # Tracking only, no output


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

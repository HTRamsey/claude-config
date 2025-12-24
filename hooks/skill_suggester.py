#!/home/jonglaser/.claude/venv/bin/python3
"""
Skill Suggester Hook - Reminds to use creator skills before creating config files.

PreToolUse hook for Write|Edit that checks if creating hooks, agents, commands, or skills
and suggests the appropriate creator skill.
"""
import json
import sys
import re
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

SUGGESTIONS = [
    {
        "pattern": r"\.claude/hooks/.*\.py$",
        "skill": "hook-creator",
        "type": "hook",
    },
    {
        "pattern": r"\.claude/agents/.*\.md$",
        "skill": "agent-creator",
        "type": "agent",
    },
    {
        "pattern": r"\.claude/commands/.*\.md$",
        "skill": "command-creator",
        "type": "command",
    },
    {
        "pattern": r"\.claude/skills/.*/SKILL\.md$",
        "skill": "skill-creator",
        "type": "skill",
    },
]

# Track suggestions per session to avoid repeating
SUGGESTION_CACHE = Path("/tmp/claude-skill-suggestions.json")

def load_cache() -> set:
    try:
        if SUGGESTION_CACHE.exists():
            with open(SUGGESTION_CACHE) as f:
                return set(json.load(f).get("suggested", []))
    except Exception:
        pass
    return set()

def save_cache(suggested: set):
    try:
        with open(SUGGESTION_CACHE, "w") as f:
            json.dump({"suggested": list(suggested)}, f)
    except Exception:
        pass

@graceful_main("skill_suggester")
def main():
    try:
        ctx = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = ctx.get("tool_name", "")
    if tool_name not in ("Write", "Edit"):
        sys.exit(0)

    tool_input = ctx.get("tool_input", {})
    file_path = tool_input.get("file_path", "")

    if not file_path:
        sys.exit(0)

    # Check each pattern
    for rule in SUGGESTIONS:
        if re.search(rule["pattern"], file_path):
            # Check if we already suggested this skill recently
            cache = load_cache()
            cache_key = f"{rule['skill']}:{Path(file_path).name}"

            if cache_key in cache:
                sys.exit(0)  # Already suggested, don't repeat

            # Add to cache
            cache.add(cache_key)
            save_cache(cache)

            result = {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "approve",
                    "permissionDecisionReason": (
                        f"📝 Creating {rule['type']} file. "
                        f"Consider using the `{rule['skill']}` skill for correct format and patterns. "
                        f"Load with: Skill(skill=\"{rule['skill']}\")"
                    )
                }
            }
            print(json.dumps(result))
            break

    sys.exit(0)

if __name__ == "__main__":
    main()

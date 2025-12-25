---
name: hook-creator
description: Create native Claude Code hooks (Python scripts). Use when creating files in ~/.claude/hooks/, when user asks to "create a hook", "add a hook", "make a PreToolUse/PostToolUse hook", or when adding entries to settings.json hooks section.
---

# Hook Creator

**Persona:** Defensive programmer creating fail-safe hooks - prioritizes silent failure over breaking workflows.

Create native Claude Code hooks - Python scripts that run before/after tool calls.

## Hook Types

| Event | When It Runs | Common Uses |
|-------|--------------|-------------|
| `PreToolUse` | Before tool executes | Block, warn, suggest alternatives |
| `PostToolUse` | After tool completes | Cache results, chain to other tools, log |
| `UserPromptSubmit` | When user sends message | Context monitoring, input validation |
| `Stop` | When Claude stops | Session persistence, uncommitted reminders |

## Critical: Output Format

**All hooks must return JSON with `hookSpecificOutput`:**

```python
# PreToolUse - approve/deny/block
result = {
    "hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "approve",  # or "deny", "block"
        "permissionDecisionReason": "Message shown to Claude"
    }
}

# PostToolUse - informational message
result = {
    "hookSpecificOutput": {
        "hookEventName": "PostToolUse",
        "message": "Message shown to Claude"
    }
}

# UserPromptSubmit - same as PreToolUse format
result = {
    "hookSpecificOutput": {
        "hookEventName": "UserPromptSubmit",
        "permissionDecision": "approve",
        "permissionDecisionReason": "Message if not approved"
    }
}
```

**WRONG formats (will cause errors):**
```python
# BAD - old format
{"decision": "approve", "message": "..."}

# BAD - missing hookSpecificOutput wrapper
{"permissionDecision": "approve", "permissionDecisionReason": "..."}
```

## Context Fields Available

| Field | Available In | Contains |
|-------|--------------|----------|
| `tool_name` | Pre/Post | Tool name: "Bash", "Edit", "Task", etc. |
| `tool_input` | Pre/Post | Tool parameters (dict) |
| `tool_result` | PostToolUse only | Tool output (dict or str) |
| `cwd` | All | Current working directory |
| `session_id` | All | Session identifier |

**Detect Pre vs Post:**
```python
if "tool_result" in ctx:
    # PostToolUse
else:
    # PreToolUse
```

## Hook Template

```python
#!/usr/bin/env python3
"""
{Description of what this hook does}.

{Event} hook for {Tool} tool.
"""
import json
import sys

def main():
    try:
        ctx = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)  # Silent failure

    tool_name = ctx.get("tool_name", "")
    tool_input = ctx.get("tool_input", {})

    # Early exit if not our target tool
    if tool_name != "TargetTool":
        sys.exit(0)

    # Your logic here
    should_warn = False  # Replace with actual check

    if should_warn:
        result = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "approve",
                "permissionDecisionReason": "Warning message here"
            }
        }
        print(json.dumps(result))

    sys.exit(0)

if __name__ == "__main__":
    main()
```

## Settings.json Configuration

Add hook to `~/.claude/settings.json`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash|Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "$HOME/.claude/hooks/my_hook.py",
            "timeout": 1
          }
        ]
      }
    ]
  }
}
```

**Matcher patterns:**
- Single tool: `"Bash"`
- Multiple tools: `"Bash|Edit|Write"`
- All tools: `"*"` or omit matcher

## Permission Decisions

| Decision | Effect |
|----------|--------|
| `approve` | Allow tool, show message |
| `deny` | Block tool, show reason |
| `block` | Hard block (same as deny) |
| (no output) | Silent approval |

## Should NOT Attempt

- Complex logic that might timeout (keep under 1s)
- Side effects in PreToolUse hooks (only decide, don't act)
- Blocking without clear reason (frustrates workflow)
- Denying based on uncertain heuristics
- Network calls in hooks (too slow, may fail)
- Reading large files (use caching instead)

## Failure Behavior

**Always fail silently.** A broken hook should never block work:

```python
def main():
    try:
        ctx = json.load(sys.stdin)
        # ... your logic ...
    except Exception:
        pass  # Silent failure
    finally:
        sys.exit(0)  # Always exit 0
```

**Never:**
- Exit with non-zero codes
- Print error messages to stdout
- Let exceptions propagate

## Escalation Triggers

| Situation | Escalate To |
|-----------|-------------|
| Hook denies frequently | Rethink rule - consider skill or agent instead |
| Logic too complex for 1s timeout | `agent-creator` skill for subagent |
| Multiple hooks conflict | User to resolve priority/ordering |
| Requires human judgment | User clarification or manual intervention |

## Best Practices

1. **Silent on success**: Return nothing if no action needed
2. **Timeout of 1s**: Keep hooks fast, use 1-5s timeout max
3. **Graceful errors**: Catch all exceptions, exit 0 on failure
4. **No side effects in Pre**: PreToolUse should only decide, not act
5. **Cache expensive ops**: Use /tmp for caching

## Examples

### Block Dangerous Commands (PreToolUse)
```python
#!/usr/bin/env python3
import json, sys, re

DANGEROUS = [r"rm\s+-rf\s+/", r"chmod\s+777", r">\s*/dev/sd"]

try:
    ctx = json.load(sys.stdin)
    if ctx.get("tool_name") != "Bash":
        sys.exit(0)

    cmd = ctx.get("tool_input", {}).get("command", "")
    for pattern in DANGEROUS:
        if re.search(pattern, cmd):
            print(json.dumps({
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": f"Blocked dangerous command: {cmd[:50]}"
                }
            }))
            break
except Exception:
    pass
sys.exit(0)
```

### Log Tool Usage (PostToolUse)
```python
#!/usr/bin/env python3
import json, sys
from datetime import datetime
from pathlib import Path

try:
    ctx = json.load(sys.stdin)
    log = Path("/tmp/claude_tool_log.jsonl")
    entry = {
        "time": datetime.now().isoformat(),
        "tool": ctx.get("tool_name"),
        "success": "error" not in str(ctx.get("tool_result", "")).lower()
    }
    with open(log, "a") as f:
        f.write(json.dumps(entry) + "\n")
except Exception:
    pass
sys.exit(0)
```

### Unified Pre/Post Hook
```python
#!/usr/bin/env python3
import json, sys

try:
    ctx = json.load(sys.stdin)
    tool_name = ctx.get("tool_name", "")

    if "tool_result" in ctx:
        # PostToolUse logic
        pass
    else:
        # PreToolUse logic
        pass
except Exception:
    pass
sys.exit(0)
```

## Validation

Test hook before adding to settings:
```bash
echo '{"tool_name": "Bash", "tool_input": {"command": "ls"}}' | python3 ~/.claude/hooks/my_hook.py
```

Verify syntax:
```bash
python3 -m py_compile ~/.claude/hooks/my_hook.py
```

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Wrong output format | Use `hookSpecificOutput` wrapper |
| Checking `hook_type` field | Check for `tool_result` instead |
| Using `tool_response` | Use `tool_result` |
| Exit code 1/2 on error | Always `sys.exit(0)` |
| Long timeouts | Keep under 5s, prefer 1s |
| Printing debug output | Only print JSON result |
| No exception handling | Wrap everything in try/except |

## Related Skills

- **skill-creator**: Create skills that use hooks
- **agent-creator**: Create agents that complement hooks
- **command-creator**: Create commands that trigger hooks

## When Blocked

If unable to create a working hook:
- Verify the hook event type exists
- Check if the use case is better suited for an agent
- Consider if a command/skill is more appropriate
- Simplify the logic to meet timeout constraints

# Config Design Patterns

Anti-patterns and best practices for ~/.claude configuration.

## Anti-Patterns

| Don't | Why | Instead |
|-------|-----|---------|
| Keep counts of agents/skills/commands | Goes stale, maintenance burden | Let scripts count dynamically |
| Duplicate content across files | Drift, inconsistency | Single source of truth, reference it |
| Hardcode paths in multiple places | Breaks on reorganization | Use variables or reference architecture.md |
| Create agents for single-use tasks | Bloat, never used again | Just do the task inline |
| Over-specialize agents | Too many to remember | Merge related capabilities |
| Generic agents without clear triggers | Never invoked | Specific triggers in description |

## Agent Design

| Do | Don't |
|----|-------|
| Minimal tool set needed | Give all tools "just in case" |
| Clear trigger words in description | Vague descriptions |
| Delegate to specialists | Duplicate expertise |
| Specify output format | Leave format unspecified |
| Include "When NOT to Use" section | Assume scope is obvious |
| Route simple tasks to Haiku | Use Opus for everything |

## Hook Design

| Do | Don't |
|----|-------|
| Use dispatchers for PreToolUse/PostToolUse | Register hooks individually |
| Fail gracefully (hook_utils.py patterns) | Let errors crash |
| Target specific tools only | Watch all tools unnecessarily |
| Keep under 100ms latency | Block on slow operations |
| Log to hook-events.jsonl | Print to stdout |

## File Organization

| Do | Don't |
|----|-------|
| One source of truth per concept | Scatter related info |
| Update architecture.md when adding components | Add files without documentation |
| Use creator skills for new config | Create files manually |
| Delete unused config | Leave dead code "just in case" |

## Documentation

| Do | Don't |
|----|-------|
| Tables over prose | Long paragraphs |
| Examples over explanations | Abstract descriptions |
| Link to authoritative source | Duplicate content |
| Keep reference.md as index only | Put details in reference.md |

## Maintenance

| Do | Don't |
|----|-------|
| Run health-check.sh after changes | Assume changes work |
| Check usage-stats.json before deleting | Delete based on gut feeling |
| Update cross-references after moves | Leave broken references |
| Validate with validate-config.sh | Skip validation |

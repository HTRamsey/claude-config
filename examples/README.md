# Examples

Reference examples for Claude Code configuration.

## Directory Structure

```
examples/
├── hooks/      # PreToolUse/PostToolUse hook templates
├── agents/     # Task subagent definitions
├── skills/     # On-demand workflow definitions
├── commands/   # Slash command definitions
└── patterns/   # Common code patterns
```

## Usage

These are templates - copy and modify for your needs:

```bash
# Copy a hook template
cp examples/hooks/example_pretool_hook.py hooks/my_hook.py

# Copy an agent template
cp examples/agents/example-agent.md agents/my-agent.md
```

## Creating New Configs

Use the creator skills instead of copying these directly:

| Creating | Use |
|----------|-----|
| Hook | `Skill(hook-creator)` |
| Agent | `Skill(agent-creator)` |
| Command | `Skill(command-creator)` |
| Skill | `Skill(skill-creator)` |

The creator skills provide interactive guidance and validation.

## See Also

- `rules/reference.md` - Quick reference for all skills, agents, commands
- `rules/architecture.md` - Full configuration map

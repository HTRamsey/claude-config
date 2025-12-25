# Archived Agents

This directory contains agents that are not currently in active use but may be useful in the future.

## Why Archive?

1. **Reduce token overhead** - Fewer active agents means less context loaded
2. **Cleaner agent list** - Easier to find relevant agents
3. **Preserve functionality** - Agents can be restored when needed

## How to Archive

Move unused agents here:
```bash
mv ~/.claude/agents/unused-agent.md ~/.claude/agents/archive/
```

## How to Restore

Move back to active directory:
```bash
mv ~/.claude/agents/archive/needed-agent.md ~/.claude/agents/
```

## Finding Unused Agents

Run the usage report:
```bash
~/.claude/scripts/diagnostics/usage-report.sh
```

This shows which agents haven't been used recently.

## Archival Criteria

Consider archiving agents that:
- Haven't been used in 30+ days
- Overlap significantly with other agents
- Are too specialized for regular use

## Currently Archived

(Agents moved here will be listed automatically)

# Archived Commands

Slash commands not currently in active use.

## Archive/Restore

```bash
# Archive
mv ~/.claude/commands/unused-cmd.md ~/.claude/commands/archive/

# Restore
mv ~/.claude/commands/archive/needed-cmd.md ~/.claude/commands/
```

## Find Unused Commands

```bash
~/.claude/scripts/diagnostics/usage-report.sh
```

## Archival Criteria

- Not used in 30+ days
- Duplicates built-in functionality
- Too specialized for regular use

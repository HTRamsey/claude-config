# Archived Skills

Skills not currently in active use.

## Archive/Restore

```bash
# Archive (move entire skill directory)
mv ~/.claude/skills/unused-skill ~/.claude/skills/archive/

# Restore
mv ~/.claude/skills/archive/needed-skill ~/.claude/skills/
```

## Find Unused Skills

```bash
~/.claude/scripts/diagnostics/usage-report.sh
```

## Archival Criteria

- Not used in 30+ days
- Overlaps with other skills
- Too specialized for regular use

## Note

Skills are directories containing `SKILL.md` and optional scripts. Archive the entire directory to preserve all components.

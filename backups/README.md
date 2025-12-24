# Configuration Backups

Versioned backups of active configuration files.

## Structure

```
backups/
├── settings/    # settings.json versions
├── hooks/       # Hook script backups
├── agents/      # Agent definition backups
├── commands/    # Command backups
├── skills/      # Skill backups
└── rules/       # Rule file backups
```

## Create Backup

```bash
# Quick backup of all config
~/.claude/scripts/backup-config.sh

# Backup specific component
~/.claude/scripts/backup-config.sh settings
~/.claude/scripts/backup-config.sh hooks
```

## Restore

```bash
# List available backups
ls -la ~/.claude/backups/settings/

# Restore specific backup
cp ~/.claude/backups/settings/settings.json.2024-12-24 ~/.claude/settings.json
```

## Automatic Backups

The `precompact_save.py` hook creates transcript backups before compaction.
Consider running `backup-config.sh` before major configuration changes.

## Retention

Backups older than 30 days can be cleaned with:
```bash
find ~/.claude/backups -type f -mtime +30 -delete
```

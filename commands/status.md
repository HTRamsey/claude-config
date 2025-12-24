---
description: Quick health check of current session, repository, and usage stats
---

Show a quick status overview of the current session, repository, and usage stats.

## Process

Run these checks and display a concise summary:

### 1. Git Status
```bash
git status --short
git stash list
```
- Count: uncommitted files, stashed changes
- Show branch and ahead/behind if applicable

### 2. Recent Activity
```bash
git log --oneline -5
```
- Show last 5 commits

### 3. Usage Stats
```bash
~/.claude/scripts/usage-report.sh --json
```
Parse `~/.claude/data/usage-stats.json` and show:
- Top 3 agents by usage count
- Top 3 skills by usage count
- Top 3 commands by usage count
- Today's activity (if any)

### 4. Context Health
- Note if context feels large (suggest /compact if needed)

### 5. Config Health
```bash
~/.claude/scripts/diagnostics/health-check.sh --quick 2>/dev/null || true
```
- Hook status (any errors in recent hook-events.jsonl)
- Data file sizes (warn if large)

## Output Format

```
## Status

**Branch**: main (2 ahead, 1 behind origin)
**Uncommitted**: 3 files modified, 1 untracked
**Stashes**: 2

**Recent commits**:
- abc1234 Fix login bug
- def5678 Add user profile
- ghi9012 Update deps

**Top Usage**:
| Type | Name | Uses |
|------|------|------|
| Agent | Explore | 42 |
| Agent | code-reviewer | 18 |
| Skill | verification-before-completion | 12 |
| Command | commit | 31 |

**Today**: 5 agents, 2 skills, 8 commands

**Health**:
✓ No whitespace issues
✓ Hooks OK
⚠ Consider /compact (context is large)
```

## Rules
- Keep output concise (fit in one screen)
- Highlight actionable items (uncommitted changes, stashes)
- Only show warnings if there are actual issues
- Skip usage section if no data exists yet
- For full usage report, suggest `~/.claude/scripts/usage-report.sh`

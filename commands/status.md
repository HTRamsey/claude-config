---
description: Quick health check of current session and repository
---

Show a quick status overview of the current session and repository.

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

### 3. Context Health
- Note if context feels large (suggest /compact if needed)

### 4. Repository Health
```bash
# Check for common issues
git diff --check  # whitespace errors
```

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

**Health**:
✓ No whitespace issues
⚠ Consider /compact (context is large)
```

## Rules
- Keep output concise (fit in one screen)
- Highlight actionable items (uncommitted changes, stashes)
- Only show warnings if there are actual issues

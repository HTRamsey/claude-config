---
description: Generate changelog from git commits
---

Generate a changelog from git commits between two points.

## Arguments
- `$ARGUMENTS` - Optional: tag range (e.g., "v1.0.0..v1.1.0") or "since:DATE"

## Process

1. **Determine range**
   - If tag range provided: use it
   - If "since:DATE" provided: use `--since=DATE`
   - If no args: since last tag or last 20 commits

2. **Get commits**
   ```bash
   git log --oneline --no-merges <range>
   ```

3. **Categorize by conventional commit type**
   - `feat:` → Features
   - `fix:` → Bug Fixes
   - `perf:` → Performance
   - `docs:` → Documentation
   - `refactor:` → Refactoring
   - `test:` → Tests
   - `chore:` → Maintenance
   - Other → Other Changes

4. **Format output**
   ```markdown
   ## [Version] - YYYY-MM-DD

   ### Features
   - Description (commit hash)

   ### Bug Fixes
   - Description (commit hash)

   ### Other Changes
   - Description (commit hash)
   ```

## Rules
- Group commits by type
- Use commit message (without type prefix) as description
- Include short commit hash for reference
- Skip merge commits
- If no conventional commits, list all under "Changes"

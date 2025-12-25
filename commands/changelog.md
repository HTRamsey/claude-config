---
description: Generate changelog from git commits
---

Generate a changelog from git commits between two points.

## Arguments
- `$ARGUMENTS` - Optional: tag range (e.g., "v1.0.0..v1.1.0") or "since:DATE"

## Workflow

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

## Output Format
```markdown
## [v1.2.0] - 2025-01-15

### Features
- Add battery voltage display (a1b2c3d)
- Support dark mode toggle (e4f5g6h)

### Bug Fixes
- Fix GPS timeout handling (i7j8k9l)

### Documentation
- Update installation guide (m0n1o2p)
```

## Example Output

```markdown
## [v2.3.0] - 2025-12-20

### Features
- Add parallel subagent execution to config-audit (5f8a2c1)
- Support section-specific audit in /config-audit command (6d9b3e2)
- Implement unified cache for exploration and research (7e0c4f3)

### Bug Fixes
- Fix hook timeout configuration validation (8f1d5a4)
- Resolve duplicate hook registration in dispatcher (9g2e6b5)

### Documentation
- Update architecture.md with dispatcher workflow (0h3f7c6)

### Maintenance
- Refactor pre_tool_dispatcher.py for clarity (1i4g8d7)
- Add health-check script tests (2j5h9e8)
```

## Should NOT Do
- Edit or rewrite commit messages
- Include merge commits
- Add entries not from git history
- Guess version numbers (ask user)

## When to Bail
- No commits in specified range
- Unable to determine version/tag info (ask user)
- Over 500 commits (ask to narrow range)

## Rules
- Group commits by type
- Use commit message (without type prefix) as description
- Include short commit hash for reference
- Skip merge commits
- If no conventional commits, list all under "Changes"

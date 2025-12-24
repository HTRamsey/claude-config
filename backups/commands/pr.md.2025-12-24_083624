---
description: Create a well-structured pull request
allowed-tools: Bash(git:*), Bash(gh:*), Read, Grep
argument-hint: [--draft] [--base <branch>]
---

# /pr

Create a pull request with a well-structured description.

## Options
$ARGUMENTS (--draft for draft PR, --base <branch> for target branch)

## Workflow

1. **Check prerequisites:**
   ```bash
   # Ensure we're on a feature branch
   git branch --show-current

   # Check for uncommitted changes
   git status --short

   # Verify remote tracking
   git rev-parse --abbrev-ref --symbolic-full-name @{u} 2>/dev/null || echo "No upstream"
   ```

2. **Gather context:**
   ```bash
   # Get base branch (default: main or master)
   git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@'

   # List commits not in base
   git log --oneline origin/main..HEAD 2>/dev/null || git log --oneline origin/master..HEAD

   # Get diff summary
   git diff --stat origin/main..HEAD 2>/dev/null || git diff --stat origin/master..HEAD
   ```

3. **Push branch if needed:**
   ```bash
   git push -u origin $(git branch --show-current)
   ```

4. **Create PR:**
   ```bash
   gh pr create --title "<type>(<scope>): <description>" --body "$(cat <<'EOF'
   ## Summary
   <1-3 bullet points describing what this PR does>

   ## Changes
   - <file or component>: <what changed>

   ## Testing
   - [ ] <how to test>

   ## Related
   - Closes #<issue> (if applicable)
   EOF
   )"
   ```

5. **Report result:**
   - Show PR URL
   - Show any CI checks that started

## PR Title Format
Follow conventional commits:
- `feat(scope): add new feature`
- `fix(scope): resolve bug`
- `docs(scope): update documentation`
- `refactor(scope): restructure code`
- `test(scope): add tests`
- `chore(scope): maintenance`

## Rules
- Push commits before creating PR
- Use meaningful title (< 72 chars)
- Include testing instructions
- Link related issues
- Never include AI attribution
- Add `--draft` flag for work-in-progress

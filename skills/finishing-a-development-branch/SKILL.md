---
name: finishing-a-development-branch
description: Use when implementation is complete, all tests pass, and you need to decide how to integrate the work - guides completion of development work by presenting structured options for merge, PR, or cleanup
---

# Finishing a Development Branch

**Persona:** Methodical release engineer who treats every merge as a potential production deployment.

**Core principle:** Verify tests -> Present options -> Execute choice -> Clean up.

**Announce:** "I'm using the finishing-a-development-branch skill to complete this work."

## Should NOT Attempt

- Merge without green tests (escalate to debugging)
- Auto-select options without user input
- Push to protected branches directly
- Delete branches that have open PRs
- Handle complex merge conflicts (escalate to git-expert agent)

## Process

### 1. Verify Tests
Run test suite. **If tests fail:** Show failures, stop. Cannot proceed until green.

### 2. Determine Base Branch
```bash
git merge-base HEAD main 2>/dev/null || git merge-base HEAD master
```

### 3. Present Options
```
Implementation complete. What would you like to do?

1. Merge back to <base-branch> locally
2. Push and create a Pull Request
3. Keep the branch as-is (I'll handle it later)
4. Discard this work

Which option?
```

### 4. Execute Choice

| Option | Actions |
|--------|---------|
| 1. Merge | checkout base, pull, merge, test, delete branch, cleanup worktree |
| 2. PR | push -u, gh pr create, keep worktree |
| 3. Keep | Report location, keep worktree |
| 4. Discard | **Require typed "discard" confirmation**, delete branch, cleanup worktree |

### 5. Cleanup Worktree
- Options 1, 4: `git worktree remove <path>`
- Options 2, 3: Keep worktree

## Escalation Triggers

| Situation | Escalate To |
|-----------|-------------|
| Merge conflicts beyond simple resolution | `git-expert` agent |
| Tests fail after merge | `systematic-debugging` skill |
| CI failures on pushed branch | `ci-fix` command |
| Protected branch rejection | Ask user for guidance |
| Rebase required with complex history | `git-expert` agent |

## Failure Behavior

- **Tests fail:** Stop, show failures, explain that tests must pass before proceeding
- **Merge conflict:** Attempt auto-resolve; if not trivial, escalate to git-expert
- **Push rejected:** Report reason (permissions, hooks, protected branch), ask user
- **gh CLI fails:** Report error, provide manual PR creation instructions

## Quick Reference

| Option | Merge | Push | Keep Worktree | Cleanup Branch |
|--------|-------|------|---------------|----------------|
| 1 | Y | - | - | Y |
| 2 | - | Y | Y | - |
| 3 | - | - | Y | - |
| 4 | - | - | - | Y (force) |

## Never

- Proceed with failing tests
- Merge without verifying tests on result
- Delete work without confirmation
- Force-push without explicit request

## Called By

- `subagent-driven-development` (Step 7)
- `executing-plans` (Step 5)

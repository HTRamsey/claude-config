---
name: git-workflow
description: Use when starting feature work that needs isolation, or when completing work and deciding how to integrate - covers full worktree lifecycle from setup through merge/PR/discard
---

# Git Workflow

**Persona:** Careful workspace manager who ensures isolation, tracks progress, and handles clean completion.

## Overview

Full git worktree lifecycle: create isolated workspace → do work → complete with merge/PR/keep/discard.

**Core principle:** Systematic setup + safety verification + structured completion = reliable workflow.

**Announce at start:** "I'm using the git-workflow skill to [set up an isolated workspace / complete this work]."

## When to Use

| Trigger | Phase |
|---------|-------|
| Starting feature that needs isolation | Setup |
| Before executing implementation plans | Setup |
| Implementation complete, tests pass | Completion |
| Ready to merge, create PR, or cleanup | Completion |

## Should NOT Attempt

- Create worktrees for simple single-file changes (overkill)
- Nest worktrees inside other worktrees
- Proceed with failing tests (setup or completion)
- Delete work without typed confirmation

---

## Phase 1: Setup

### Directory Selection

Follow this priority order:

**1. Check existing directories:**
```bash
ls -d .worktrees 2>/dev/null     # Preferred (hidden)
ls -d worktrees 2>/dev/null      # Alternative
```

**2. Check CLAUDE.md** for preference.

**3. Ask user** if no directory exists:
```
No worktree directory found. Where should I create worktrees?

1. .worktrees/ (project-local, hidden)
2. ~/.local/share/claude-worktrees/<project-name>/ (global)

Which?
```

### Safety Verification

**For project-local directories:**

MUST verify .gitignore before creating:
```bash
grep -q "^\.worktrees/$" .gitignore || grep -q "^worktrees/$" .gitignore
```

If NOT in .gitignore: Add immediately + commit before proceeding.

### Creation Steps

```bash
# 1. Detect project name
project=$(basename "$(git rev-parse --show-toplevel)")

# 2. Create worktree
git worktree add "$path" -b "$BRANCH_NAME"
cd "$path"

# 3. Run setup (auto-detect)
[ -f package.json ] && npm install
[ -f Cargo.toml ] && cargo build
[ -f requirements.txt ] && pip install -r requirements.txt
[ -f go.mod ] && go mod download

# 4. Verify baseline
npm test / cargo test / pytest / go test ./...
```

**If tests fail:** Report failures, ask whether to proceed or investigate.

**If tests pass:** Report ready:
```
Worktree ready at <full-path>
Tests passing (<N> tests, 0 failures)
Ready to implement <feature-name>
```

---

## Phase 2: Completion

### Step 1: Verify Tests

**Before presenting options:**
```bash
npm test / cargo test / pytest / go test ./...
```

**If tests fail:** Stop. Cannot proceed until tests pass.

### Step 2: Determine Base Branch

```bash
git merge-base HEAD main 2>/dev/null || git merge-base HEAD master 2>/dev/null
```

### Step 3: Present Options

Present exactly these 4 options:
```
Implementation complete. What would you like to do?

1. Merge back to <base-branch> locally
2. Push and create a Pull Request
3. Keep the branch as-is (I'll handle it later)
4. Discard this work

Which option?
```

### Step 4: Execute Choice

#### Option 1: Merge Locally
```bash
git checkout <base-branch>
git pull
git merge <feature-branch>
<test command>  # Verify merged result
git branch -d <feature-branch>
```
Then: Cleanup worktree.

#### Option 2: Push and Create PR
```bash
git push -u origin <feature-branch>
gh pr create --title "<title>" --body "$(cat <<'EOF'
## Summary
<2-3 bullets>

## Test Plan
- [ ] <verification steps>
EOF
)"
```
Then: Keep worktree (for PR revisions).

#### Option 3: Keep As-Is
Report: "Keeping branch <name>. Worktree preserved at <path>."

#### Option 4: Discard
**Confirm first:**
```
This will permanently delete:
- Branch <name>
- All commits: <commit-list>
- Worktree at <path>

Type 'discard' to confirm.
```

Wait for exact confirmation. Then:
```bash
git checkout <base-branch>
git branch -D <feature-branch>
```
Then: Cleanup worktree.

### Step 5: Cleanup Worktree

**For Options 1 and 4:**
```bash
git worktree list | grep $(git branch --show-current)
git worktree remove <worktree-path>
```

**For Options 2 and 3:** Keep worktree.

---

## Quick Reference

### Setup
| Situation | Action |
|-----------|--------|
| `.worktrees/` exists | Use it (verify .gitignore) |
| `worktrees/` exists | Use it (verify .gitignore) |
| Neither exists | Check CLAUDE.md → Ask user |
| Directory not in .gitignore | Add + commit immediately |
| Tests fail during baseline | Report + ask |

### Completion
| Option | Merge | Push | Keep Worktree | Cleanup Branch |
|--------|-------|------|---------------|----------------|
| 1. Merge locally | ✓ | - | - | ✓ |
| 2. Create PR | - | ✓ | ✓ | - |
| 3. Keep as-is | - | - | ✓ | - |
| 4. Discard | - | - | - | ✓ (force) |

---

## Common Mistakes

**Skipping .gitignore verification**
- Worktree contents get tracked, pollute git status
- Fix: Always verify before creating project-local worktree

**Skipping test verification**
- Merge broken code or create failing PR
- Fix: Always verify tests before setup completion AND before finish options

**Automatic worktree cleanup**
- Remove worktree when might need it (Option 2, 3)
- Fix: Only cleanup for Options 1 and 4

**No confirmation for discard**
- Accidentally delete work
- Fix: Require typed "discard" confirmation

---

## Red Flags

**Never:**
- Proceed with failing tests
- Merge without verifying tests on result
- Delete work without confirmation
- Force-push without explicit request
- Create worktree without .gitignore check

**Always:**
- Verify tests at setup and completion
- Present exactly 4 completion options
- Get typed confirmation for Option 4
- Report full paths for worktrees

---

## Failure Behavior

### Setup
- **Branch exists:** Offer to use existing or create with suffix
- **Directory exists:** Ask whether to reuse or create new
- **Git worktree fails:** Show error, suggest `git worktree prune`
- **Dependency install fails:** Warn tests may fail, proceed
- **Tests fail:** Report, require permission to continue

### Completion
- **Tests fail:** Stop, show failures, require fixes
- **Merge conflict:** Report, offer to resolve or abort
- **PR creation fails:** Show error, check gh auth status

---

## Escalation Triggers

| Situation | Escalate To |
|-----------|-------------|
| Tests fail during baseline | Ask: proceed or investigate? |
| Unknown project type | Ask for setup commands |
| Complex merge needed | `git-expert` agent |
| .gitignore modification rejected | Ask user to handle |
| Merge conflicts | Ask: resolve or abort? |

---

## Integration

**Called by:**
- **subagent-driven-development** - When tasks need isolated workspace
- **incremental-implementation** - For feature branches

**Pairs with:**
- **git-expert** agent - For complex branch operations
- **/pr** command - Option 2 uses PR workflow
- **/worktree** command - Basic worktree operations

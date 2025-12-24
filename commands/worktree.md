---
description: Manage git worktrees for parallel development sessions
---

Help me manage git worktrees. Based on the argument provided:

**If no argument or "list":** Show existing worktrees with `git worktree list`

**If "add <branch>":** Create a new worktree:
1. Check if branch exists locally or remotely
2. Create worktree in `../$(basename $PWD)-<branch>/`
3. Report the path so I can open another Claude session there

**If "remove <branch>":** Remove worktree safely:
1. Check for uncommitted changes
2. Run `git worktree remove <path>`
3. Optionally delete the branch if requested

**Common workflow:**
```bash
# Create worktree for feature branch
git worktree add ../myproject-feature feature-branch

# Work in parallel (separate terminal)
cd ../myproject-feature && claude

# When done, remove worktree
git worktree remove ../myproject-feature
```

Execute the appropriate git worktree commands based on what I requested.

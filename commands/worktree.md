---
description: Manage git worktrees for parallel development sessions
allowed-tools: Bash(git:*)
argument-hint: [list|add <branch>|remove <branch>]
---

# /worktree

Manage git worktrees for parallel development sessions.

## Arguments
$ARGUMENTS - One of: `list`, `add <branch>`, or `remove <branch>`

## Workflow

### list (default)
Show existing worktrees:
```bash
git worktree list
```

### add <branch>
Create a new worktree:
1. Check if branch exists locally or remotely
2. Create worktree in `../$(basename $PWD)-<branch>/`
3. Report the path for opening another Claude session

```bash
git worktree add ../myproject-<branch> <branch>
```

### remove <branch>
Remove worktree safely:
1. Check for uncommitted changes - warn if present
2. Run `git worktree remove <path>`
3. Optionally delete the branch if requested

## Rules

- Never remove a worktree with uncommitted changes without warning
- Always report the full path after creating a worktree
- Check if branch exists before creating worktree

## Output

```
Worktree created: /path/to/project-feature
Branch: feature-branch
Ready for: cd /path/to/project-feature && claude
```

## Examples

```
/worktree list
→ Show all worktrees

/worktree add feature-auth
→ Create worktree for feature-auth branch

/worktree remove feature-auth
→ Remove the feature-auth worktree
```

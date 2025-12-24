---
description: Iteratively fix CI failures on PR until all checks pass
allowed-tools: Bash(gh:*), Bash(git:*), Read, Edit, Grep, Glob
argument-hint: [pr-number]
---

# CI Fix - Iteratively fix CI failures on PR

Automatically monitor, diagnose, and fix CI workflow failures until the PR passes.

## Workflow

```
┌─────────────┐
│  Check CI   │◄────────────────┐
└──────┬──────┘                 │
       │                        │
       ▼                        │
   ┌───────┐    Yes   ┌─────────┴─────────┐
   │ Pass? ├─────────►│       Done        │
   └───┬───┘          └───────────────────┘
       │ No
       ▼
┌─────────────┐
│ Fetch Logs  │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Diagnose   │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│    Fix      │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ Commit/Push │──────────────────┘
└─────────────┘
```

## Instructions

You are fixing CI failures for a pull request. Follow this cycle:

### Step 1: Identify the PR
```bash
# Get current branch's PR
gh pr view --json number,title,headRefName,state,statusCheckRollup
```

If no PR argument provided and no PR exists for current branch, ask the user.

### Step 2: Check CI Status
```bash
# List all workflow runs for the PR
gh pr checks

# Get detailed status
gh run list --branch $(git branch --show-current) --limit 5
```

If all checks pass, report success and exit.

### Step 3: Fetch Failed Workflow Logs
```bash
# Get the failed run ID
gh run list --branch $(git branch --show-current) --status failure --limit 1 --json databaseId,name,conclusion

# Download logs for failed run
gh run view <run-id> --log-failed
```

Use `compress-build.sh` or `compress-tests.sh` to reduce log output if verbose.

### Step 4: Diagnose the Failure

Common CI failure categories:
- **Build errors**: Compilation, type errors, missing dependencies
- **Test failures**: Unit/integration test failures
- **Lint errors**: ESLint, Prettier, Black, Ruff
- **Type check errors**: TypeScript, mypy, pyright
- **Security scan**: Dependency vulnerabilities
- **Format check**: Code formatting violations

Analyze the error output and identify:
1. Which files need changes
2. What specific errors occurred
3. Root cause (not just symptoms)

### Step 5: Fix the Issues

Apply fixes following these principles:
- Fix root cause, not symptoms
- Run local verification before pushing:
  ```bash
  # Match CI environment locally
  npm test        # or pytest, cargo test, go test
  npm run lint    # or ruff, black, eslint
  npm run build   # or make, cargo build
  ```
- Make minimal changes - only fix what's broken

### Step 6: Commit and Push
```bash
# Stage and commit the fix
git add -A
git commit -m "fix(ci): <describe what was fixed>"

# Push to trigger new CI run
git push
```

### Step 7: Wait and Re-check
```bash
# Wait for CI to start (usually 10-30 seconds)
sleep 30

# Check new run status
gh run list --branch $(git branch --show-current) --limit 1

# Watch the run (optional, for long-running CI)
gh run watch
```

Return to Step 2 and repeat until all checks pass.

## Guardrails

- **Max iterations**: Stop after 5 fix attempts and ask for human review
- **Scope creep**: Only fix CI errors, don't refactor unrelated code
- **Breaking changes**: If fix requires API/interface changes, confirm with user first
- **Flaky tests**: If same test fails intermittently, note it as flaky, don't keep retrying

## Output Format

After each cycle, report:
```
## CI Fix Cycle N

**Status**: ❌ Failed / ✅ Passed
**Failed Checks**: <list>
**Errors Found**: <summary>
**Fixes Applied**: <list of changes>
**Next**: Pushing fix... / Done!
```

## Completion

When all checks pass:
```
## CI Passed ✅

All workflow checks are now passing.
- Cycles needed: N
- Files modified: <list>
- Ready for review/merge
```

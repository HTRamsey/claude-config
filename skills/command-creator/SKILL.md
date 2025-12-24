---
name: command-creator
description: Create slash commands (/command). Use when creating files in ~/.claude/commands/ or .claude/commands/, when user asks to "create a command", "add a slash command", "make /something", or when defining new /workflows.
---

# Command Creator

**Persona:** UX designer for CLI workflows - prioritizes discoverability, predictable behavior, and safe defaults.

Create slash commands that users invoke with `/name`.

## Command vs Skill vs Agent

| Type | Location | Trigger | Purpose |
|------|----------|---------|---------|
| Command | `commands/` | `/name` explicit | User-initiated workflows |
| Skill | `skills/` | Auto or explicit | Procedural knowledge |
| Agent | `agents/` | `Task(subagent_type)` | Subagent execution |

**Commands** = User-facing shortcuts for common workflows.

## Command Location

```
~/.claude/commands/          # Global commands
.claude/commands/            # Project commands (override global)
```

## Creation Process

### Step 1: Initialize
```bash
~/.claude/skills/command-creator/scripts/init_command.py <name> --description "<description>" [--global]
```

Example:
```bash
~/.claude/skills/command-creator/scripts/init_command.py deploy --description "Deploy to production" --global
```

### Step 2: Edit the Command
Complete the TODO sections in the generated file:
- Define workflow steps with bash examples
- Add example outputs
- List anti-patterns
- Add escalation triggers

### Step 3: Test
Invoke the command to verify it works:
```
/command-name
```

## Template

```markdown
# /{command-name}

{One-line description of what this command does.}

## Workflow

1. **{Step name}:**
   ```bash
   {example command}
   ```

2. **{Step name}:**
   - {Action item}
   - {Action item}

3. **{Step name}:**
   ```bash
   {example command}
   ```

## Examples
{Show 2-3 example outputs}

## Should NOT Do
- {Anti-pattern}
- {Anti-pattern}

## When to Bail
{When the command should stop and ask for guidance}

## Rules
- {Constraint}
- {Constraint}
```

## Should NOT Attempt

- Auto-committing without explicit request
- Auto-pushing to remote
- Destructive operations without confirmation
- Making decisions that require domain knowledge
- Continuing after errors without user acknowledgment

## Failure Behavior

When a command can't proceed:
1. State what step failed and why
2. Show relevant error output
3. Suggest how to proceed manually
4. Don't attempt recovery without asking

Example:
```markdown
## When to Bail
- Tests fail before refactoring starts (unsafe to proceed)
- Uncommitted changes exist (might lose work)
- Can't identify scope of changes (ask for clarification)
```

## Escalation Triggers

| Situation | Escalate To |
|-----------|-------------|
| Task complexity exceeds command scope | `/understand` or `orchestrator` agent |
| Security implications detected | `/review` with security focus |
| Multi-step reasoning beyond workflow | `Plan` agent for architecture |
| Conflicting constraints | User clarification |

Add explicit escalation guidance to commands:
```markdown
## Escalation
If this requires architecture decisions, recommend `/understand` first.
If security concerns arise, recommend running `/review` with security focus.
```

## Examples

### /commit
```markdown
# /commit

Create a conventional commit from staged changes.

## Workflow

1. **Check state:**
   ```bash
   git status --short
   git diff --cached --stat
   ```

2. **Analyze changes:**
   - Determine type: feat|fix|docs|refactor|test|chore
   - Identify scope (component affected)

3. **Commit:**
   ```bash
   git commit -m "type(scope): clear subject"
   ```

## Examples
```
feat(auth): add OAuth2 login flow
fix(api): handle null response correctly
```

## Should NOT Do
- Push automatically
- Amend previous commits
- Add unstaged files without asking

## When to Bail
- No staged changes (nothing to commit)
- Staged changes include sensitive files

## Rules
- No AI attribution
- No emojis
- Subject < 50 chars
```

### /review
```markdown
# /review

Review current changes for issues.

## Workflow

1. **Get changes:**
   ```bash
   git diff HEAD
   ```

2. **Analyze for:**
   - Security issues (OWASP Top 10)
   - Performance problems
   - Code quality issues
   - Missing tests

3. **Report findings:**
   | Severity | File:Line | Issue | Fix |
   |----------|-----------|-------|-----|

## Should NOT Do
- Apply fixes automatically
- Make subjective style judgments

## When to Bail
- No changes to review
- Binary files only

## Rules
- Focus on substantive issues
- Include fix suggestions
- Skip style nitpicks
```

### /test
```markdown
# /test

Run tests and analyze failures.

## Workflow

1. **Run tests:**
   ```bash
   npm test 2>&1 | head -100
   ```

2. **On failure:**
   - Identify failing test
   - Read test file
   - Analyze expected vs actual
   - Propose fix

3. **Report:**
   - X passed
   - Y failed: [reason]

## Should NOT Do
- Auto-fix failing tests
- Delete/skip failing tests

## When to Bail
- No test framework detected
- Tests require manual setup (DB, env vars)

## Escalation
If test failures indicate design issues, recommend `/understand` to explore the codebase first.
```

### /refactor
```markdown
# /refactor

Refactor code safely with tests.

## Workflow

1. **Verify tests pass:**
   ```bash
   npm test
   ```

2. **Analyze target code:**
   - Identify code smells
   - Plan refactoring steps
   - Check dependencies

3. **Refactor incrementally:**
   - One change at a time
   - Run tests after each change

4. **Verify:**
   ```bash
   npm test
   ```

## Should NOT Do
- Refactor without passing tests first
- Change behavior (only structure)
- Make multiple changes at once

## When to Bail
- Tests don't pass initially
- Refactoring would change API contracts
- No clear improvement measurable

## Escalation
If refactoring affects public API, recommend creating a migration plan first.

## Rules
- Never refactor without passing tests
- Preserve behavior exactly
- Commit after each safe step
```

## Command Design Principles

1. **Single purpose**: One command = one workflow
2. **Predictable**: Same input → same process
3. **Safe by default**: Don't auto-commit/push
4. **Show progress**: Indicate what's happening
5. **Fail gracefully**: Handle errors clearly
6. **Bail early**: Stop and ask rather than guess

## Naming Conventions

| Pattern | Examples |
|---------|----------|
| Action verbs | `/commit`, `/review`, `/test`, `/build` |
| Nouns for tools | `/docs`, `/changelog`, `/worktree` |
| Compound for specific | `/batch-review`, `/tech-debt` |

Avoid:
- Generic names: `/do`, `/run`, `/go`
- Abbreviations: `/cmt`, `/rv`
- Conflicts with builtins: `/help`, `/clear`, `/config`

## Registration

Commands in `~/.claude/commands/` are auto-discovered.

Invoke: `/command-name` or `/command-name arguments`

## Advanced: With Arguments

Commands receive arguments after the name:

```markdown
# /search

Search codebase for pattern.

**Arguments**: `$ARGUMENTS` - search pattern

## Workflow
1. Parse pattern from `$ARGUMENTS`
2. Run search:
   ```bash
   rg "$ARGUMENTS" --type-add 'code:*.{ts,js,py}' -t code
   ```
3. Show results
```

Usage: `/search handleAuth`

## Validation

Test command:
```bash
# Check file exists
ls ~/.claude/commands/my-command.md

# Verify structure
head -30 ~/.claude/commands/my-command.md
```

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Too complex | Split into multiple commands |
| No examples | Add 2-3 concrete examples |
| Missing rules | Add constraints section |
| Vague steps | Use specific commands |
| Auto-destructive | Require confirmation for destructive ops |
| No bail conditions | Add "When to Bail" section |
| No anti-patterns | Add "Should NOT Do" section |

## When Blocked

If unable to create a working command:
- Clarify the exact workflow steps
- Check if an existing command already covers this
- Consider if a skill is more appropriate (procedural knowledge vs workflow)
- Consider if an agent is more appropriate (delegation vs user-initiated)

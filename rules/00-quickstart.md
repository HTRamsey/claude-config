# Quickstart Guide

Get productive in 5 minutes.

## Essential Commands

| Command | When to Use |
|---------|-------------|
| `/review` | Before committing - checks security, performance, quality |
| `/commit` | Create a well-formatted commit |
| `/test` | Diagnose test failures |
| `/debug` | Systematic debugging with root cause analysis |

See `05-context.md` for all 14 slash commands.

## Key Agents (via Task tool)

| Task | Agent | Model |
|------|-------|-------|
| Quick lookup | `quick-lookup` | Haiku |
| Explore codebase | `Explore` (built-in) | Haiku |
| Plan implementation | `Plan` (built-in) | Default |
| Code review | `code-reviewer` | Opus |
| Security review | `security-reviewer` | Opus |
| Claude Code questions | `claude-code-guide` (built-in) | Haiku |

See `04-skills.md` for all 23 custom + 3 built-in agents.

## Optimization Scripts

```bash
# Search (97% token savings)
~/.claude/scripts/offload-grep.sh 'pattern' ./src 10

# Compress large output
~/.claude/scripts/compress-diff.sh HEAD~3
~/.claude/scripts/compress-build.sh < build.log

# Preview large files (99% savings)
~/.claude/scripts/smart-preview.sh large-file.cc
```

## Before You Start

1. **Read the file first** - Never edit without reading
2. **Use agents for exploration** - Don't grep inline, use `Task(Explore)`
3. **Compress output** - Always compress diffs, builds, test output
4. **Verify before done** - Run tests, show evidence (see `02-security.md`)
5. **Clear between tasks** - Use `/clear` to reset context
6. **Name sessions** - Use `/rename` for easy resumption

## Where to Find Things

| Need | Location |
|------|----------|
| Style rules | `~/.claude/rules/01-style.md` |
| Security rules | `~/.claude/rules/02-security.md` |
| Optimization | `~/.claude/rules/03-optimization.md` |
| All agents | `~/.claude/agents/` |
| All commands | `~/.claude/commands/` |
| All scripts | `~/.claude/scripts/` |
| Architecture | `~/.claude/rules/architecture.md` |

## Health Check

Run `~/.claude/scripts/health-check.sh` to verify setup.

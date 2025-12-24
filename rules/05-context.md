# Context & Configuration

## Hooks (27 active)

### PreToolUse
- File protection, Credential scanner (at commit), TDD Guard
- Dangerous command blocker, Tool optimization suggestions
- File access tracker, Pre-read summarize, Context checkpoint

### PostToolUse
- Notify complete, Batch detector, Tool tracker
- Exploration cache, Agent chaining, Token tracker, Output size monitor

### Other
- Context monitor (40K/80K warning), Session persistence, Uncommitted reminder
- Start viewer (launches claude-code-viewer if not running)
- Skill suggester, Suggest subagent, Smart permissions
- Precompact save, Research cache, Subagent complete

## Commands (14 total)
`/checkpoint` `/ci-fix` `/commit` `/debug` `/docs` `/flow` `/implement` `/pr` `/queue` `/refactor` `/review` `/tech-debt` `/test` `/worktree`

**Task Queue**: `/queue add "task" --agent TYPE` | `/queue daemon start|stop`
**Orchestration**: `/flow <workflow> "objective"` (feature, security-review, refactor, quick-review, docs)

## Plugins
clangd (C++), pyright (Python)

## Context Loading

**Progressive disclosure** - Load incrementally:
1. Start narrow: Only files directly relevant
2. Expand as needed: Follow imports when required
3. Use summaries: `smart-preview.sh` for large files

## Ignore Patterns

Never read (waste tokens):
- `**/node_modules/**`, `**/vendor/**`, `**/build/**`, `**/dist/**`
- `**/*.min.js`, `**/*.min.css`, `**/.git/**`
- `**/*.log`, `**/*.lock`, `**/coverage/**`, `**/__pycache__/**`

## Session Management

| Action | Command |
|--------|---------|
| Name session | `/rename auth-refactor` |
| Resume by name | `claude --resume auth-refactor` |
| Custom session ID | `--session-id my-task --resume` |
| Fork session | `/rewind` (creates grouped fork) |

## Compaction (/compact)

**Preserve**: Task context, file paths, errors, test results
**Discard**: Processed file contents, dead-end searches, verbose outputs

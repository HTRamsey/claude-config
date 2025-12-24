# Tooling & Context

Tools, scripts, optimization, and context management.

## LSP Tool (Code Intelligence)

Use for precise navigation instead of grep:

| Operation | Use For |
|-----------|---------|
| `goToDefinition` | Jump to symbol definition |
| `findReferences` | Find all usages of symbol |
| `hover` | Get type info and docs |
| `documentSymbol` | List all symbols in file |
| `incomingCalls` | What calls this function? |
| `outgoingCalls` | What does this function call? |

## Scripts (`~/.claude/scripts/`)

| Category | Location | Scripts |
|----------|----------|---------|
| Search | `search/` | `offload-grep.sh`, `offload-find.sh` |
| Compress | `compress/` | `compress-diff.sh`, `compress-build.sh`, `compress-tests.sh`, `compress-stacktrace.sh` |
| Smart View | `smart/` | `smart-preview.sh`, `smart-diff.sh`, `smart-cat.sh`, `summarize-file.sh`, `extract-signatures.sh` |
| Analysis | `analysis/` | `find-related.sh`, `project-overview.sh`, `review-patterns.sh`, `impact-analysis.sh` |
| Git | `git/` | `git-prep.sh`, `git-cleanup.sh` |
| Queue | `queue/` | `task-queue.sh`, `queue-runner.sh` |
| Diagnostics | `diagnostics/` | `health-check.sh`, `validate-config.sh`, `hook-benchmark.sh`, `test-hooks.sh` |
| Automation | `automation/` | `claude-safe.sh`, `batch-process.sh`, `parallel.sh`, `fan-out.sh` |

## Output Compression

**ALWAYS** compress before displaying:
- Git diffs: `compress/compress-diff.sh`
- Build logs: `compress/compress-build.sh`
- Test output: `compress/compress-tests.sh`
- Stack traces: `compress/compress-stacktrace.sh`

## Modern CLI Tools

Auto-suggested by `suggest_tool_optimization.py` hook:
- **Search**: `rg` (10x faster), `fd` (4x faster)
- **View**: `bat`, `eza`
- **Diff**: `delta`, `difft`
- **Data**: `jq`, `yq`, `gron`, `htmlq`

## Token Budget

| Content | Max | Strategy |
|---------|-----|----------|
| Search results | 20 lines | head_limit param |
| File previews | 100 lines | smart-preview.sh |
| Code blocks | 50 lines | Excerpt + reference |
| Diffs/Build/Test | Errors only | compress-*.sh |

## Haiku Routing (80-90% Cost Savings)

**Route to Haiku**: Single-file ops, "What/Where is X?", error explanations, summarization.
**Keep on Opus**: Architecture, complex debugging, security, code review, refactoring.

## Background & Resume Patterns

- **Long-running agents**: Use `run_in_background=true`
- **Iterative work**: Resume agents with `resume=<agent_id>`

## Context Management

- **Clear between tasks**: `/clear` resets context, improves focus
- **File references**: Use `@src/file.ts` to include file + its CLAUDE.md chain
- **Session resume**: `claude --resume <name>` preserves context across sessions
- **Auto-compact**: Triggers at ~80% capacity; manual `/compact` preserves more

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

## Extended Thinking

- **Toggle**: **Alt+T**
- **Trigger words**: Prefix with "ultrathink:" for complex architecture
- **Use for**: Architectural decisions, challenging bugs, multi-step planning

## Hooks (27 + 2 dispatchers)

### PreToolUse (via pre_tool_dispatcher.py)
- File protection, Credential scanner (at commit), TDD Guard
- Dangerous command blocker, Tool optimization suggestions
- File access tracker, Pre-read summarize, Context checkpoint

### PostToolUse (via post_tool_dispatcher.py)
- Notify complete, Batch detector, Tool tracker
- Exploration cache, Agent chaining, Token tracker, Output size monitor

### Other Events
- Context monitor (40K/80K warning), Session persistence, Uncommitted reminder
- Skill suggester, Suggest subagent, Smart permissions
- Precompact save, Research cache, Subagent complete

## Plugins

clangd (C++), pyright (Python)

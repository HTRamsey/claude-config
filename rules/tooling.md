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
| Compress | `compress/` | `compress.sh --type diff\|build\|tests\|stack\|logs\|json\|list\|errors` |
| Smart View | `smart/` | `smart-view.sh` (unified viewer), `smart-analyze.sh` (unified analysis), `smart-diff.sh`, `smart-json.sh`, `smart-yaml.sh`, `smart-html.sh`, `smart-http.sh`, `smart-ast.sh`, `smart-blame.sh`, `smart-ls.sh`, `smart-du.sh`, `smart-find.sh`, `smart-replace.sh`, `extract-signatures.sh` |
| Analysis | `analysis/` | `project-stats.sh`, `review-patterns.sh`, `token-tools.sh` (use `smart-analyze.sh` for deps/impact) |
| Git | `git/` | `git-prep.sh`, `git-cleanup.sh` |
| Queue | `queue/` | `task-queue.sh`, `queue-runner.sh` |
| Diagnostics | `diagnostics/` | `health-check.sh`, `validate-config.sh`, `hook-benchmark.sh`, `test-hooks.sh`, `statusline.sh`, `venv-setup.sh`, `usage-report.sh`, `backup-config.sh`, `skills-ref.sh` |
| Automation | `automation/` | `claude-safe.sh`, `batch-process.sh`, `parallel.sh`, `fan-out.sh`, `session-picker.sh`, `init-project-rules.sh`, `quick-jump.sh`, `recall.sh` |

## Output Compression

**ALWAYS** compress before displaying:
- Git diffs: `compress/compress.sh --type diff`
- Build logs: `compress/compress.sh --type build`
- Test output: `compress/compress.sh --type tests`
- Stack traces: `compress/compress.sh --type stack`
- Log files: `compress/compress.sh --type logs`
- JSON data: `compress/compress.sh --type json`
- Long lists: `compress/compress.sh --type list`
- Repeated errors: `compress/compress.sh --type errors`

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
| Diffs/Build/Test | Errors only | compress.sh |

## Haiku Routing (80-90% Cost Savings)

**Route to Haiku**: Single-file ops, "What/Where is X?", error explanations, summarization.
**Keep on Opus**: Architecture, complex debugging, security, code review, refactoring.

## Task Tool Settings

| Parameter | Default | When to Change |
|-----------|---------|----------------|
| `model` | sonnet | haiku: lookups, summaries; opus: security, architecture |
| `timeout` | 120s | Increase for: large codebases, slow builds, complex analysis |
| `run_in_background` | false | Long tasks (>30s), parallel investigation |

### Timeout Guidelines

| Task Type | Recommended |
|-----------|-------------|
| Quick lookup, simple edit | 60s |
| Code review, test generation | 120s (default) |
| Large codebase exploration | 300s |
| Full build + test | 600s (max) |

### Background Execution

Use `run_in_background=true` when:
- Task will take >30 seconds
- Running multiple agents in parallel
- Want to continue working while agent runs

Retrieve results with `TaskOutput(task_id, block=true)`.

### Model Selection

| Model | Cost | Use For |
|-------|------|---------|
| haiku | $ | quick-lookup, batch-editor, doc-generator, summarization |
| sonnet | $$ | Most agents (default) |
| opus | $$$ | orchestrator, code-reviewer, migration-planner, security |

### Resume Pattern

- **Iterative work**: Resume agents with `resume=<agent_id>`
- Agent continues with full previous context preserved
- Use for follow-up questions or extending previous work

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
| Session history | Stored in `data/session-history.json` |

## Compaction (/compact)

**Preserve**: Task context, file paths, errors, test results
**Discard**: Processed file contents, dead-end searches, verbose outputs

## Extended Thinking

- **Toggle**: **Alt+T**
- **Trigger words**: Prefix with "ultrathink:" for complex architecture
- **Use for**: Architectural decisions, challenging bugs, multi-step planning

## Hooks

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

## MCP Servers

See `architecture.md` for MCP server configuration.

## Plugins

clangd (C++), pyright (Python - currently disabled)

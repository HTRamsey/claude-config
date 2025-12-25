# Configuration Architecture

Map of Claude Code customizations at `~/.claude/`.

## Directory Structure

```
~/.claude/
├── CLAUDE.md              # Entry point, references rules
├── settings.json          # Permissions, model config
├── pyproject.toml         # Python dependencies for hooks
├── venv/                  # Python venv (auto-used via PATH)
├── rules/                 # Auto-loaded instruction files (4 files)
│   ├── guidelines.md      # Style, security, verification
│   ├── tooling.md         # Tools, scripts, context
│   ├── reference.md       # Skills, agents, commands
│   └── architecture.md    # This file
├── hooks/                 # Event-triggered Python scripts
├── agents/                # Task tool subagent definitions
├── commands/              # Slash command definitions
├── skills/                # Loaded-on-demand workflows
├── scripts/               # Shell utilities (organized)
│   ├── search/            # offload-grep, offload-find
│   ├── compress/          # compress.sh (unified)
│   ├── smart/             # smart-*, summarize-file, extract-signatures
│   ├── analysis/          # find-related, project-overview, etc.
│   ├── git/               # git-prep, git-cleanup
│   ├── queue/             # task-queue, queue-runner
│   ├── diagnostics/       # health-check, validate-config, etc.
│   ├── automation/        # claude-safe, batch-process, etc.
│   ├── lib/               # common, cache, lock, notify
│   └── tests/             # smoke-test, validation scripts
└── data/                  # Runtime data (caches, logs)
```

## Path-Specific Rules

Use YAML frontmatter to apply rules only to matching file paths:

```yaml
---
paths: src/api/**/*.ts
---
# API-Specific Rules
- All endpoints must validate input
- Use `backend-architect` agent for new endpoints
```

Supported patterns: `**/*.ts`, `src/**/*`, `{src,lib}/**/*.ts`

## Hooks

**Shared Utilities**: `hook_utils.py` provides graceful degradation, JSON logging, session state.
**Dispatchers (ACTIVE)**: `pre_tool_dispatcher.py` and `post_tool_dispatcher.py` consolidate all PreToolUse/PostToolUse hooks into single processes. ~200ms latency savings per tool call.

### PreToolUse (block/modify before execution)
| Hook | Watches | Purpose |
|------|---------|---------|
| `file_protection` | Write, Edit | Block protected files |
| `credential_scanner` | Bash (git commit) | Detect secrets in staged changes |
| `tdd_guard` | Write, Edit | Warn if no tests for code changes |
| `dangerous_command_blocker` | Bash | Block destructive commands |
| `suggestion_engine` | Write, Edit, Bash, Grep, Glob, Read | Unified suggestions (skills, subagents, tool optimization) |
| `file_monitor` | Read, Edit | Track reads, detect stale context, suggest summarization |
| `state_saver` | Edit, Write | Save checkpoint before risky edits |

### PostToolUse (react after execution)
| Hook | Watches | Purpose |
|------|---------|---------|
| `notify_complete` | Bash | Desktop notification for long commands |
| `file_monitor` | Grep, Glob, Read | Detect duplicate searches/reads |
| `batch_operation_detector` | Edit, Write | Suggest batching similar edits |
| `tool_success_tracker` | all | Track failures, suggest alternatives |
| `unified_cache` | Task, WebFetch | Cache exploration and research results |
| `suggestion_engine` | Task | Suggest specialist follow-ups (agent chaining) |
| `usage_tracker` | Task, Skill | Track agent/skill/command usage |
| `output_metrics` | all | Track tokens and warn about large outputs |
| `build_analyzer` | Bash | Parse build failures, summarize errors, suggest fixes |
| `smart_permissions` | Read, Edit, Write | Learn permission patterns for auto-approval |

### Other Events
| Hook | Event | Purpose |
|------|-------|---------|
| `session_start` | SessionStart | Auto-load git context on new session |
| `context_monitor` | UserPromptSubmit | Warn at 40K/80K tokens, auto-backup |
| `session_persistence` | SessionEnd | Auto-save session insights |
| `uncommitted_reminder` | Stop | Remind about uncommitted changes |
| `start_viewer` | SessionStart | Start claude-code-viewer |
| `smart_permissions` | PermissionRequest | Context-aware auto-approval with learning |
| `state_saver` | PreCompact | Backup transcript before compaction |
| `subagent_start` | SubagentStart | Track subagent spawn time |
| `subagent_complete` | SubagentStop | Handle subagent completion, calculate duration |

## Scripts

Organized into subdirectories:

| Directory | Purpose | Key Scripts |
|-----------|---------|-------------|
| `search/` (2) | Offloaded search | `offload-grep.sh`, `offload-find.sh` |
| `compress/` (1) | Output compression | `compress.sh --type diff\|build\|tests\|stack\|logs\|json\|list\|errors` |
| `smart/` (17) | Smart file viewing | `smart-view.sh` (unified viewer), `smart-analyze.sh` (unified analysis), `smart-preview.sh`, `smart-cat.sh`, `smart-diff.sh`, `smart-json.sh`, `smart-yaml.sh`, `smart-html.sh`, `smart-http.sh`, `smart-ast.sh`, `smart-blame.sh`, `smart-ls.sh`, `smart-du.sh`, `smart-find.sh`, `smart-replace.sh`, `extract-signatures.sh`, `summarize-file.sh` |
| `analysis/` (7) | Code analysis | `dependency-graph.sh`, `find-related.sh`, `impact-analysis.sh`, `project-overview.sh`, `project-stats.sh`, `review-patterns.sh`, `token-tools.sh` |
| `git/` (3) | Git workflow | `git-prep.sh`, `git-cleanup.sh`, `pre-commit-hook.sh` |
| `queue/` (2) | Task queue | `task-queue.sh`, `queue-runner.sh` |
| `diagnostics/` (9) | Health & testing | `health-check.sh`, `hook-benchmark.sh`, `hook-profiler.sh`, `validate-config.sh`, `test-hooks.sh`, `statusline.sh`, `venv-setup.sh`, `usage-report.sh`, `backup-config.sh` |
| `automation/` (13) | Batch operations | `claude-safe.sh`, `batch-process.sh`, `parallel.sh`, `fan-out.sh`, `retry.sh`, `claude-model.sh`, `claude-tmux.sh`, `batch-annotate.sh`, `batch-select.sh`, `session-picker.sh`, `init-project-rules.sh`, `quick-jump.sh`, `recall.sh` |
| `lib/` (4) | Shared utilities | `common.sh`, `cache.sh`, `lock.sh`, `notify.sh` |

Root-level: (none - all scripts organized into subdirectories)

## Data Flow

```
User Input
    │
    ├─→ PreToolUse hooks (via pre_tool_dispatcher.py)
    │
    ├─→ Tool execution
    │       │
    │       ├─→ Task tool → Subagent (uses agents/*.md)
    │       ├─→ Skill tool → Load skill (skills/*/SKILL.md)
    │       └─→ Bash tool → May use scripts/**/*.sh
    │
    ├─→ PostToolUse hooks (via post_tool_dispatcher.py)
    │
    └─→ Response
```

## Python Environment

Hooks use an isolated venv at `~/.claude/venv/`. The PATH is set in `settings.json` so `#!/usr/bin/env python3` automatically uses it.

| Task | Command |
|------|---------|
| Check status | `~/.claude/scripts/diagnostics/venv-setup.sh check` |
| Update deps | `~/.claude/scripts/diagnostics/venv-setup.sh update` |
| Recreate | `~/.claude/scripts/diagnostics/venv-setup.sh create` |

Dependencies: `pyproject.toml` (currently: tiktoken, rapidfuzz)

## Data Rotation

Run `~/.claude/scripts/diagnostics/health-check.sh --cleanup` to:
- Delete debug files older than 7 days
- Delete file-history older than 30 days
- Delete transcript-backups older than 7 days (or trim to 10 if > 50MB)
- Rotate hook-events.jsonl if > 10MB
- Clean old temp files

## Key Files

| File | Purpose |
|------|---------|
| `settings.json` | Permissions, allowed tools, model preferences |
| `pyproject.toml` | Python dependencies for hooks |
| `rules/*.md` | Auto-loaded instructions (4 files) |
| `data/task-queue.json` | Pending background tasks |
| `data/token-usage.json` | Daily token tracking |
| `data/exploration-cache.json` | Cached codebase exploration (unified_cache) |
| `data/research-cache.json` | Cached web research (unified_cache) |
| `data/usage-stats.json` | Agent/skill/command usage tracking |
| `data/permission-patterns.json` | Learned permission patterns |
| `data/hook-events.jsonl` | Hook execution log |
| `data/session-history.json` | Session metadata for resumption |

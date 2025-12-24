# Configuration Architecture

Map of Claude Code customizations at `~/.claude/`.

## Directory Structure

```
~/.claude/
├── CLAUDE.md              # Entry point, references rules
├── settings.json          # Permissions, model config
├── requirements.txt       # Python dependencies for hooks
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
│   ├── compress/          # compress-diff, compress-build, etc.
│   ├── smart/             # smart-*, summarize-file, extract-signatures
│   ├── analysis/          # find-related, project-overview, etc.
│   ├── git/               # git-prep, git-cleanup
│   ├── queue/             # task-queue, queue-runner
│   ├── diagnostics/       # health-check, validate-config, etc.
│   ├── automation/        # claude-safe, batch-process, etc.
│   └── lib/               # common, cache, lock, notify
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

## Hooks (27 + 2 dispatchers) - Event Triggers

**Shared Utilities**: `hook_utils.py` provides graceful degradation, JSON logging, session state.
**Dispatchers (ACTIVE)**: `pre_tool_dispatcher.py` and `post_tool_dispatcher.py` consolidate all PreToolUse/PostToolUse hooks into single processes. ~200ms latency savings per tool call.

### PreToolUse (block/modify before execution)
| Hook | Watches | Purpose |
|------|---------|---------|
| `file_protection` | Write, Edit | Block protected files |
| `credential_scanner` | Bash (git commit) | Detect secrets in staged changes |
| `tdd_guard` | Write, Edit | Warn if no tests for code changes |
| `dangerous_command_blocker` | Bash | Block destructive commands |
| `suggest_tool_optimization` | Bash, Grep, Read | Suggest better alternatives |
| `file_access_tracker` | Read, Edit | Detect stale context |
| `preread_summarize` | Read | Suggest summarization for large files |
| `context_checkpoint` | Edit, Write | Save state before risky edits |

### PostToolUse (react after execution)
| Hook | Watches | Purpose |
|------|---------|---------|
| `notify_complete` | Bash | Desktop notification for long commands |
| `file_access_tracker` | Grep, Glob, Read | Track file access patterns |
| `batch_operation_detector` | Edit, Write | Suggest batching similar edits |
| `tool_success_tracker` | all | Track failures, suggest alternatives |
| `exploration_cache` | Task | Cache exploration results |
| `agent_chaining` | Task | Suggest specialist follow-ups |
| `usage_tracker` | Task, Skill | Track agent/skill/command usage |
| `token_tracker` | all | Track daily token usage |
| `output_size_monitor` | all | Warn about large outputs |

### Other Events
| Hook | Event | Purpose |
|------|-------|---------|
| `session_start` | SessionStart | Auto-load git context on new session |
| `context_monitor` | UserPromptSubmit | Warn at 40K/80K tokens, auto-backup |
| `session_persistence` | SessionEnd | Auto-save session insights |
| `uncommitted_reminder` | Stop | Remind about uncommitted changes |
| `start_viewer` | SessionStart | Start claude-code-viewer |
| `skill_suggester` | UserPromptSubmit | Suggest relevant skills |
| `suggest_subagent` | UserPromptSubmit | Suggest agent delegation |
| `smart_permissions` | PermissionRequest | Context-aware auto-approval |
| `precompact_save` | PreCompact | Save state before compaction |
| `research_cache` | PreToolUse/PostToolUse | Cache web research results |
| `subagent_complete` | SubagentStop | Handle subagent completion |

## Agents (24 custom + 3 built-in) - Specialized Subagents

### Built-in (no file needed)
`Explore` `Plan` `claude-code-guide`

### Quick Operations (Haiku)
`quick-lookup` `error-explainer`

### Research
`technical-researcher`

### Code Review & Quality
`code-reviewer` `security-reviewer`

### Architecture
`backend-architect` `database-architect` `ai-engineer`

### Operations
`devops-troubleshooter` `incident-responder` `migration-planner`

### Generation & Planning
`test-generator` `doc-generator` `orchestrator`

### Specialized
`git-expert` `cpp-expert` `context-optimizer` `batch-editor` `testing-debugger`
`cross-platform-tester` `import-optimizer` `protocol-analyzer` `real-time-systems`

### Meta (Config Management)
`claude-config-expert`

## Commands (14) - Slash Commands

| Command | Purpose |
|---------|---------|
| `/commit` | Create formatted commit |
| `/review` | Pre-commit quality review |
| `/test` | Diagnose test failures |
| `/debug` | Systematic debugging |
| `/implement` | Structured feature work |
| `/refactor` | Safe refactoring workflow |
| `/docs` | Generate documentation |
| `/pr` | Create pull request |
| `/ci-fix` | Fix CI failures iteratively |
| `/tech-debt` | Catalog technical debt |
| `/checkpoint` | Save task state |
| `/worktree` | Git worktree management |
| `/queue` | Task queue management |
| `/flow` | Claude-flow orchestration |

## Skills (16) - On-Demand Workflows

### Core Workflows
`systematic-debugging` `test-driven-development` `verification-before-completion` `security-audit`

### Quality & Process
`code-smell-detection` `receiving-code-review` `context-management`
`batch-operations` `subagent-driven-development`

### Git & Implementation
`using-git-worktrees` `incremental-implementation`

### Creators
`hook-creator` `agent-creator` `command-creator` `skill-creator`

### Specialized
`memory-management-optimization`

## Scripts (55) - Shell Utilities

Organized into subdirectories:

| Directory | Purpose | Key Scripts |
|-----------|---------|-------------|
| `search/` | Offloaded search | `offload-grep.sh`, `offload-find.sh` |
| `compress/` | Output compression | `compress-diff.sh`, `compress-build.sh`, `compress-tests.sh` |
| `smart/` | Smart file viewing | `smart-preview.sh`, `smart-diff.sh`, `summarize-file.sh` |
| `analysis/` | Code analysis | `find-related.sh`, `project-overview.sh`, `review-patterns.sh` |
| `git/` | Git workflow | `git-prep.sh`, `git-cleanup.sh` |
| `queue/` | Task queue | `task-queue.sh`, `queue-runner.sh` |
| `diagnostics/` | Health & testing | `health-check.sh`, `validate-config.sh`, `hook-benchmark.sh` |
| `automation/` | Batch operations | `claude-safe.sh`, `batch-process.sh`, `parallel.sh` |
| `lib/` | Shared utilities | `common.sh`, `cache.sh`, `lock.sh` |

Root-level: `statusline.sh`, `venv-setup.sh`, `usage-report.sh`

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
| Check status | `~/.claude/scripts/venv-setup.sh check` |
| Update deps | `~/.claude/scripts/venv-setup.sh update` |
| Recreate | `~/.claude/scripts/venv-setup.sh create` |

Dependencies: `requirements.txt` (currently: tiktoken, rapidfuzz)

## Data Rotation

Run `~/.claude/scripts/diagnostics/health-check.sh --cleanup` to:
- Delete debug files older than 7 days
- Delete file-history older than 30 days
- Rotate hook-events.jsonl if > 10MB
- Clean old temp files

## Key Files

| File | Purpose |
|------|---------|
| `settings.json` | Permissions, allowed tools, model preferences |
| `requirements.txt` | Python dependencies for hooks |
| `rules/*.md` | Auto-loaded instructions (4 files) |
| `data/task-queue.json` | Pending background tasks |
| `data/token-usage.json` | Daily token tracking |
| `data/exploration-cache.json` | Cached codebase exploration |
| `data/usage-stats.json` | Agent/skill/command usage tracking |
| `data/hook-events.jsonl` | Hook execution log |

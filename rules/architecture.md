# Configuration Architecture

Map of Claude Code customizations at `~/.claude/`.

## Directory Structure

```
~/.claude/
├── CLAUDE.md              # Entry point, references rules
├── settings.json          # Permissions, model config
├── requirements.txt       # Python dependencies for hooks
├── venv/                  # Python venv (auto-used via PATH)
├── rules/                 # Auto-loaded instruction files
├── hooks/                 # Event-triggered Python scripts
├── agents/                # Task tool subagent definitions
├── commands/              # Slash command definitions
├── skills/                # Loaded-on-demand workflows
├── scripts/               # Optimization shell scripts
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
- Use `api-designer` agent for new endpoints
```

Supported patterns: `**/*.ts`, `src/**/*`, `{src,lib}/**/*.ts`

## Hooks (26) - Event Triggers

**Shared Utilities**: `hook_utils.py` provides graceful degradation, JSON logging, session state.
**Migration Guide**: See `hooks/MIGRATION.md` for patterns.

### PreToolUse (block/modify before execution)
| Hook | Watches | Purpose |
|------|---------|---------|
| `file_protection` | Write, Edit | Block protected files |
| `credential_scanner` | Write, Edit | Detect secrets in code |
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
| `session_start` | UserPromptSubmit | Auto-load git context on new session |
| `context_monitor` | UserPromptSubmit | Warn at 40K/80K tokens, auto-backup |
| `session_persistence` | Stop | Auto-save session insights |
| `uncommitted_reminder` | Stop | Remind about uncommitted changes |
| `start_viewer` | Notification | Start claude-code-viewer |
| `skill_suggester` | UserPromptSubmit | Suggest relevant skills |
| `suggest_subagent` | UserPromptSubmit | Suggest agent delegation |
| `smart_permissions` | PermissionRequest | Context-aware auto-approval |

## Agents (23) - Specialized Subagents

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

## Scripts (57) - Shell Utilities

### Search & Compression
`offload-grep.sh` `offload-find.sh` `compress-diff.sh` `compress-build.sh` `compress-tests.sh` `compress-stacktrace.sh`

### Code Analysis
`extract-signatures.sh` `smart-preview.sh` `summarize-file.sh` `find-related.sh` `project-overview.sh`

### Modern CLI Wrappers
`smart-ls.sh` `smart-diff.sh` `smart-cat.sh` `smart-find.sh` `smart-replace.sh`

### Automation
`claude-safe.sh` `claude-model.sh` `batch-process.sh` `fan-out.sh`

### Git Workflow
`git-prep.sh` `git-cleanup.sh`

### Task Queue
`task-queue.sh` `queue-runner.sh`

## Data Flow

```
User Input
    │
    ├─→ PreToolUse hooks (validate/modify)
    │
    ├─→ Tool execution
    │       │
    │       ├─→ Task tool → Subagent (uses agents/*.md)
    │       ├─→ Skill tool → Load skill (skills/*/SKILL.md)
    │       └─→ Bash tool → May use scripts/*.sh
    │
    ├─→ PostToolUse hooks (react/log)
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

Dependencies: `requirements.txt` (currently: tiktoken)

## Key Files

| File | Purpose |
|------|---------|
| `settings.json` | Permissions, allowed tools, model preferences |
| `requirements.txt` | Python dependencies for hooks |
| `rules/*.md` | Auto-loaded instructions (5 files, ~350 lines) |
| `data/task-queue.json` | Pending background tasks |
| `data/token-usage.json` | Daily token tracking |
| `data/exploration-cache.json` | Cached codebase exploration |

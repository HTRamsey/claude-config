# Configuration Architecture

Map of Claude Code customizations at `~/.claude/`.

## Directory Structure

```
~/.claude/
├── CLAUDE.md              # Entry point, references rules
├── settings.json          # Permissions, model config
├── pyproject.toml         # Python dependencies for hooks
├── venv/                  # Python venv (auto-used via PATH)
├── rules/                 # Auto-loaded instruction files
│   ├── guidelines.md      # Style, security, verification
│   ├── tooling.md         # Tools, scripts, context
│   ├── reference.md       # Skills, agents, commands
│   └── architecture.md    # This file
├── docs/                  # Reference docs (not auto-loaded)
│   └── config-patterns.md # Anti-patterns, best practices
├── resources/             # External reference materials
│   ├── anthropic/         # Official Anthropic resources
│   │   └── skill-creator/ # Definitive skill creation guide
│   └── agentskills/       # AgentSkills SDK and spec
│       ├── skills-ref/    # Reference SDK source
│       └── docs/          # Specification docs
├── learnings/             # Accumulated insights (not auto-loaded)
│   ├── skills.md          # Skill design patterns
│   ├── hooks.md           # Hook implementation lessons
│   ├── agents.md          # Subagent patterns
│   ├── debugging.md       # Debugging insights
│   ├── workflows.md       # Process improvements
│   └── anti-patterns.md   # What NOT to do
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
**Hook SDK**: `hook_sdk.py` provides typed context objects, response builders, and common patterns.
**Dispatchers (ACTIVE)**: `pre_tool_dispatcher.py` and `post_tool_dispatcher.py` consolidate all PreToolUse/PostToolUse hooks into single processes. ~200ms latency savings per tool call.

### Hook CLI

Manage hooks with `~/.claude/scripts/diagnostics/hook-cli.sh`:

| Command | Description |
|---------|-------------|
| `list` | List all hooks and their status |
| `status [hook]` | Show detailed status (last run, errors) |
| `enable <hook>` | Enable a disabled hook |
| `disable <hook>` | Disable a hook |
| `test <hook>` | Test hook with sample input |
| `bench [hook]` | Benchmark hook latency |
| `logs [hook]` | Show recent log entries |

### Async Hooks

Shell hooks can run asynchronously by outputting JSON config as the first line:

```bash
#!/usr/bin/env bash
echo '{"async":true,"asyncTimeout":15000}'  # Run async with 15s timeout

# Rest of hook logic runs without blocking
```

Use async for hooks that:
- Perform network requests
- Run slow initialization checks
- Don't need to block tool execution

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
| `hierarchical_rules` | Read, Write, Edit | Apply per-directory CLAUDE.md rules |

### PostToolUse (react after execution)
| Hook | Watches | Purpose |
|------|---------|---------|
| `notify_complete_async.sh` | Bash | Desktop notification for long commands (async) |
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
| `session_start` | SessionStart | Auto-load git context, codebase map, project type |
| `context_monitor` | UserPromptSubmit | Warn at 40K/80K tokens, auto-backup |
| `session_persistence` | SessionEnd | Auto-save session insights |
| `uncommitted_reminder` | Stop | Remind about uncommitted changes |
| `auto_continue` | Stop | Evaluate if work should continue (rate-limited) |
| `start_viewer` | SessionStart | Start claude-code-viewer |
| `smart_permissions` | PermissionRequest | Context-aware auto-approval with learning |
| `state_saver` | PreCompact | Backup transcript, preserve CLAUDE.md/todos, learning reminder |
| `subagent_start` | SubagentStart | Track subagent spawn time |
| `subagent_complete` | SubagentStop | Handle subagent completion, calculate duration |

**Note**: Some hooks handle multiple events (`suggestion_engine`, `file_monitor`, `state_saver`, `unified_cache`, `smart_permissions`) and appear in multiple tables above.

## Scripts

Organized into subdirectories:

| Directory | Purpose | Key Scripts |
|-----------|---------|-------------|
| `search/` | Offloaded search | `offload-grep.sh`, `offload-find.sh` |
| `compress/` | Output compression | `compress.sh --type diff\|build\|tests\|stack\|logs\|json\|list\|errors` |
| `smart/` | Smart file viewing | `smart-view.sh`, `smart-analyze.sh`, `smart-diff.sh`, `smart-json.sh`, `smart-yaml.sh`, `smart-html.sh`, `smart-http.sh`, `smart-ast.sh`, `smart-blame.sh`, `smart-ls.sh`, `smart-du.sh`, `smart-find.sh`, `smart-replace.sh`, `extract-signatures.sh` |
| `analysis/` | Code analysis | `project-stats.sh`, `review-patterns.sh`, `token-tools.sh` |
| `git/` | Git workflow | `git-prep.sh`, `git-cleanup.sh`, `pre-commit-hook.sh` |
| `queue/` | Task queue | `task-queue.sh`, `queue-runner.sh` |
| `diagnostics/` | Health & testing | `health-check.sh`, `hook-cli.sh`, `hook-benchmark.sh`, `hook-profiler.sh`, `validate-config.sh`, `test-hooks.sh`, `statusline.sh`, `venv-setup.sh`, `usage-report.sh`, `backup-config.sh`, `skills-ref.sh` |
| `automation/` | Batch operations | `claude-safe.sh`, `batch-process.sh`, `parallel.sh`, `fan-out.sh`, `retry.sh`, `claude-model.sh`, `claude-tmux.sh`, `batch-annotate.sh`, `batch-select.sh`, `session-picker.sh`, `init-project-rules.sh`, `quick-jump.sh`, `recall.sh` |
| `lib/` | Shared utilities | `common.sh`, `cache.sh`, `lock.sh`, `notify.sh` |
| `tests/` | Validation | `smoke-test.sh` |

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
| `rules/*.md` | Auto-loaded instructions |
| `data/task-queue.json` | Pending background tasks |
| `data/token-usage.json` | Daily token tracking |
| `data/exploration-cache.json` | Cached codebase exploration (unified_cache) |
| `data/research-cache.json` | Cached web research (unified_cache) |
| `data/usage-stats.json` | Agent/skill/command usage tracking |
| `data/reflexion-log.json` | Subagent outcomes and lessons learned |
| `data/permission-patterns.json` | Learned permission patterns |
| `data/hook-events.jsonl` | Hook execution log |
| `data/session-history.json` | Session metadata for resumption |

## MCP Servers

Model Context Protocol servers extend Claude's capabilities with external integrations.

### Configuration

MCP servers are configured in `settings.json` under `allowedMcpServers`:

```json
"allowedMcpServers": [
  {"serverName": "memory"},
  {"serverName": "github"}
]
```

### Recommended Servers

| Server | Purpose | Use When |
|--------|---------|----------|
| **Brave Search** | Web search without WebFetch | Research, documentation lookup |
| **GitHub** | Native repo operations | PR reviews, issue management |
| **Puppeteer** | Browser automation | Testing, scraping, screenshots |
| **Memory** | Persistent knowledge graph | Cross-session context |
| **Filesystem** | File operations | Sandboxed file access |

### Installation

```bash
# Example: Install Brave Search MCP
claude mcp add brave-search

# List configured servers
claude mcp list

# Remove a server
claude mcp remove <server-name>
```

### Best Practices

- **Prefer MCP over WebFetch** when available (native integration, better reliability)
- **Limit scope** - Only enable servers you actively use
- **Security** - Review server permissions before enabling
- **Timeout config** - Set `MCP_TIMEOUT` and `MCP_TOOL_TIMEOUT` in settings.json env

### Current Status

Run `claude mcp list` or `~/.claude/scripts/diagnostics/health-check.sh` to see configured servers.

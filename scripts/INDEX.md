# Script Index

59 shell scripts for Claude Code optimization and automation.

## Quick Reference

| Need | Script |
|------|--------|
| Compress diff output | `compress-diff.sh` |
| Compress build logs | `compress-build.sh` |
| Compress test output | `compress-tests.sh` |
| Search with limits | `offload-grep.sh` |
| Find files by type | `offload-find.sh` |
| Preview large files | `smart-preview.sh` |
| Pre-commit checks | `git-prep.sh` |
| Run in parallel | `parallel.sh` |

## Categories

### Compression (9 scripts)
Output compression for token efficiency.

| Script | Purpose |
|--------|---------|
| `compress.sh` | Unified compression engine (diff/build/tests/stack/logs/json/list/errors) |
| `compress-build.sh` | Build output - errors and warnings only |
| `compress-diff.sh` | Git diff - file-level summary |
| `compress-tests.sh` | Test failures (pytest/jest/cargo/go) |
| `compress-stacktrace.sh` | Stack traces - filters framework frames |
| `compress-logs.sh` | Log filtering - errors/warnings |
| `compress-json.sh` | JSON field extraction |
| `compress-list.sh` | List filtering with limits |
| `dedup-errors.sh` | Error deduplication |

### Search & Discovery (4 scripts)
Token-efficient search operations.

| Script | Purpose |
|--------|---------|
| `offload-grep.sh` | Summarized grep with file counts |
| `offload-find.sh` | Categorized find results |
| `find-related.sh` | Find related code files |
| `offload-api.sh` | API call offloading |

### Smart Viewers (14 scripts)
Modern CLI tool wrappers with fallbacks.

| Script | Purpose | Primary Tool |
|--------|---------|--------------|
| `smart-ls.sh` | Directory listing | eza/lsd |
| `smart-cat.sh` | File viewing with line ranges | bat |
| `smart-diff.sh` | Git diff visualization | delta/difftastic |
| `smart-difft.sh` | Structural diffs | difftastic |
| `smart-find.sh` | Find results formatting | fd |
| `smart-du.sh` | Disk usage | dust |
| `smart-preview.sh` | Large file preview with structure | - |
| `smart-blame.sh` | Git blame history | - |
| `smart-json.sh` | JSON extraction | jq |
| `smart-yaml.sh` | YAML extraction | yq |
| `smart-html.sh` | HTML extraction | htmlq |
| `smart-http.sh` | HTTP response parsing | xh/curlie |
| `smart-tree.sh` | Tree view | - |
| `smart-replace.sh` | Find and replace | sd |

### Code Analysis (7 scripts)
Code structure and signature extraction.

| Script | Purpose |
|--------|---------|
| `extract-signatures.sh` | Function/class signatures (8 languages) |
| `summarize-file.sh` | File structure summaries |
| `smart-ast.sh` | Abstract syntax tree analysis |
| `project-overview.sh` | Project type detection |
| `project-stats.sh` | Project statistics |
| `token-tools.sh` | Token counting & estimation |
| `impact-analysis.sh` | Change impact analysis |

### Git Workflow (2 scripts)
Pre-commit and repository maintenance.

| Script | Purpose |
|--------|---------|
| `git-prep.sh` | Pre-commit validation (conflicts, debug, secrets, lint, tests) |
| `git-cleanup.sh` | Repository maintenance (branches, gc, prune) |

### Execution & Control (5 scripts)
Parallel execution, retries, and batching.

| Script | Purpose |
|--------|---------|
| `parallel.sh` | Parallel job runner with fail-fast and timeout |
| `retry.sh` | Exponential backoff retries |
| `fan-out.sh` | Routes tasks by scale (direct/batch/parallel) |
| `batch-process.sh` | Batch grep/read/lint/test |
| `batch-annotate.sh` | Batch annotation tools |
| `batch-select.sh` | Batch selection tools |

### Task Queue (2 scripts)
Background task management.

| Script | Purpose |
|--------|---------|
| `task-queue.sh` | Full task queue system |
| `queue-runner.sh` | Task queue runner daemon |

### Utilities (8 scripts)
Caching, locking, notifications, and helpers.

| Script | Purpose |
|--------|---------|
| `common.sh` | Shared library (logging, colors, command detection) |
| `cache.sh` | TTL-based file caching |
| `lock.sh` | File-based locking mechanism |
| `notify.sh` | Desktop notifications |
| `recall.sh` | Memory/history recall |
| `quick-jump.sh` | Quick navigation |
| `statusline.sh` | Status line display |
| `health-check.sh` | Configuration diagnostics |

### Claude Integration (3 scripts)
Safe Claude Code automation.

| Script | Purpose |
|--------|---------|
| `claude-safe.sh` | Automation safeguards (max turns, timeout, token budget) |
| `claude-model.sh` | Model selection/management |
| `claude-tmux.sh` | Tmux integration |

### Setup & Verification (3 scripts)
Environment setup and verification.

| Script | Purpose |
|--------|---------|
| `venv-setup.sh` | Python venv management |
| `init-project-rules.sh` | Project initialization |
| `verify-optimizations.sh` | Optimization verification |

### Analysis (1 script)
Subscription and model analysis.

| Script | Purpose |
|--------|---------|
| `evaluate-subscription.sh` | Model/subscription cost analysis |

## Common Patterns

### Using Compression Scripts
```bash
# Compress git diff
~/.claude/scripts/compress-diff.sh HEAD~3

# Compress build output
make 2>&1 | ~/.claude/scripts/compress-build.sh

# Compress test output
pytest -v 2>&1 | ~/.claude/scripts/compress-tests.sh

# JSON output for automation
~/.claude/scripts/compress.sh -t diff --json HEAD~3 | jq '.files'
```

### Using Search Scripts
```bash
# Summarized grep (max 10 results)
~/.claude/scripts/offload-grep.sh 'pattern' ./src 10

# Find by extension
~/.claude/scripts/offload-find.sh ./src '*.ts'
```

### Using Parallel Execution
```bash
# Run 3 commands in parallel
~/.claude/scripts/parallel.sh 3 "npm test" "npm lint" "npm build"

# With timeout and fail-fast
~/.claude/scripts/parallel.sh --timeout 60 -f 4 "cmd1" "cmd2" "cmd3"
```

## Dependencies

### Required
- bash 4.0+
- coreutils (standard Unix tools)

### Optional (for enhanced features)
| Tool | Scripts | Fallback |
|------|---------|----------|
| `rg` (ripgrep) | offload-grep, parallel | grep |
| `fd` | offload-find, smart-find | find |
| `bat` | smart-cat | cat |
| `eza` | smart-ls | ls |
| `delta` | smart-diff | git diff |
| `jq` | compress, smart-json, cache | passthrough |
| `yq` | smart-yaml | - |
| `htmlq` | smart-html | - |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CLAUDE_SCRIPTS` | `~/.claude/scripts` | Script directory |
| `LOG_LEVEL` | `3` | Logging verbosity (1-4) |
| `MAX_LINES` | `50` | Default line limit for compression |
| `MAX_PARALLEL` | `4` | Default parallel job limit |

## See Also

- `~/.claude/rules/architecture.md` - Full configuration map
- `~/.claude/rules/03-optimization.md` - Optimization guidelines
- `~/.claude/hooks/` - Event-triggered hooks

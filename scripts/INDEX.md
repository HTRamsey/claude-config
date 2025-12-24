# Script Index

55 shell scripts organized into 9 subdirectories.

## Quick Reference

| Need | Script |
|------|--------|
| Compress diff output | `compress/compress-diff.sh` |
| Compress build logs | `compress/compress-build.sh` |
| Compress test output | `compress/compress-tests.sh` |
| Search with limits | `search/offload-grep.sh` |
| Find files by type | `search/offload-find.sh` |
| Preview large files | `smart/smart-preview.sh` |
| Pre-commit checks | `git/git-prep.sh` |
| Run in parallel | `automation/parallel.sh` |
| Health check | `diagnostics/health-check.sh` |

## Directory Structure

```
scripts/
├── search/        # Offloaded search operations
├── compress/      # Output compression
├── smart/         # Modern CLI wrappers
├── analysis/      # Code analysis
├── git/           # Git workflow
├── queue/         # Task queue
├── diagnostics/   # Health & testing
├── automation/    # Batch operations
├── lib/           # Shared utilities
└── (root)         # Core utilities
```

## Categories

### search/ (2 scripts)
Token-efficient search operations.

| Script | Purpose |
|--------|---------|
| `offload-grep.sh` | Summarized grep with file counts |
| `offload-find.sh` | Categorized find results |

### compress/ (5 scripts)
Output compression for token efficiency.

| Script | Purpose |
|--------|---------|
| `compress.sh` | Unified compression engine |
| `compress-build.sh` | Build output - errors and warnings only |
| `compress-diff.sh` | Git diff - file-level summary |
| `compress-tests.sh` | Test failures (pytest/jest/cargo/go) |
| `compress-stacktrace.sh` | Stack traces - filters framework frames |

### smart/ (15 scripts)
Modern CLI tool wrappers with fallbacks.

| Script | Purpose | Primary Tool |
|--------|---------|--------------|
| `smart-ls.sh` | Directory listing | eza/lsd |
| `smart-cat.sh` | File viewing with line ranges | bat |
| `smart-diff.sh` | Git diff visualization | delta/difftastic |
| `smart-find.sh` | Find results formatting | fd |
| `smart-du.sh` | Disk usage | dust |
| `smart-preview.sh` | Large file preview with structure | - |
| `smart-blame.sh` | Git blame history | - |
| `smart-json.sh` | JSON extraction | jq |
| `smart-yaml.sh` | YAML extraction | yq |
| `smart-html.sh` | HTML extraction | htmlq |
| `smart-http.sh` | HTTP response parsing | xh/curlie |
| `smart-replace.sh` | Find and replace | sd |
| `smart-ast.sh` | Abstract syntax tree analysis | ast-grep |
| `extract-signatures.sh` | Function/class signatures | - |
| `summarize-file.sh` | File structure summaries | - |

### analysis/ (6 scripts)
Code structure and project analysis.

| Script | Purpose |
|--------|---------|
| `find-related.sh` | Find related code files |
| `project-overview.sh` | Project type detection |
| `project-stats.sh` | Project statistics |
| `token-tools.sh` | Token counting & estimation |
| `impact-analysis.sh` | Change impact analysis |
| `review-patterns.sh` | Code review patterns |

### git/ (2 scripts)
Git workflow helpers.

| Script | Purpose |
|--------|---------|
| `git-prep.sh` | Pre-commit validation (conflicts, debug, secrets, lint, tests) |
| `git-cleanup.sh` | Repository maintenance (branches, gc, prune) |

### queue/ (2 scripts)
Background task management.

| Script | Purpose |
|--------|---------|
| `task-queue.sh` | Full task queue system |
| `queue-runner.sh` | Task queue runner daemon |

### diagnostics/ (4 scripts)
Health checking and testing.

| Script | Purpose |
|--------|---------|
| `health-check.sh` | Configuration diagnostics (use --cleanup for data rotation) |
| `validate-config.sh` | Config validation |
| `hook-benchmark.sh` | Hook latency profiling |
| `test-hooks.sh` | Hook testing framework |

### automation/ (9 scripts)
Batch operations and Claude integration.

| Script | Purpose |
|--------|---------|
| `parallel.sh` | Parallel job runner with fail-fast and timeout |
| `retry.sh` | Exponential backoff retries |
| `fan-out.sh` | Routes tasks by scale (direct/batch/parallel) |
| `batch-process.sh` | Batch grep/read/lint/test |
| `batch-annotate.sh` | Batch annotation tools |
| `batch-select.sh` | Batch selection tools |
| `claude-safe.sh` | Automation safeguards |
| `claude-model.sh` | Model selection/management |
| `claude-tmux.sh` | Tmux integration |

### lib/ (4 scripts)
Shared utilities (sourced by other scripts).

| Script | Purpose |
|--------|---------|
| `common.sh` | Shared library (logging, colors, command detection) |
| `cache.sh` | TTL-based file caching |
| `lock.sh` | File-based locking mechanism |
| `notify.sh` | Desktop notifications |

### Root Level (6 scripts)
Core utilities that don't fit categories.

| Script | Purpose |
|--------|---------|
| `statusline.sh` | Status line display |
| `venv-setup.sh` | Python venv management |
| `usage-report.sh` | Usage statistics report |
| `init-project-rules.sh` | Project initialization |
| `quick-jump.sh` | Quick navigation |
| `recall.sh` | Memory/history recall |

## Common Patterns

### Using Compression Scripts
```bash
# Compress git diff
~/.claude/scripts/compress/compress-diff.sh HEAD~3

# Compress build output
make 2>&1 | ~/.claude/scripts/compress/compress-build.sh

# Compress test output
pytest -v 2>&1 | ~/.claude/scripts/compress/compress-tests.sh
```

### Using Search Scripts
```bash
# Summarized grep (max 10 results)
~/.claude/scripts/search/offload-grep.sh 'pattern' ./src 10

# Find by extension
~/.claude/scripts/search/offload-find.sh ./src '*.ts'
```

### Using Parallel Execution
```bash
# Run 3 commands in parallel
~/.claude/scripts/automation/parallel.sh 3 "npm test" "npm lint" "npm build"

# With timeout and fail-fast
~/.claude/scripts/automation/parallel.sh --timeout 60 -f 4 "cmd1" "cmd2" "cmd3"
```

### Data Rotation
```bash
# Clean up old data files
~/.claude/scripts/diagnostics/health-check.sh --cleanup
```

## Dependencies

### Required
- bash 4.0+
- coreutils (standard Unix tools)

### Optional (for enhanced features)
| Tool | Scripts | Fallback |
|------|---------|----------|
| `rg` (ripgrep) | search/offload-grep, automation/parallel | grep |
| `fd` | search/offload-find, smart/smart-find | find |
| `bat` | smart/smart-cat | cat |
| `eza` | smart/smart-ls | ls |
| `delta` | smart/smart-diff | git diff |
| `jq` | compress/*, smart/smart-json, lib/cache | passthrough |
| `yq` | smart/smart-yaml | - |
| `htmlq` | smart/smart-html | - |

## See Also

- `~/.claude/rules/architecture.md` - Full configuration map
- `~/.claude/rules/tooling.md` - Optimization guidelines
- `~/.claude/hooks/` - Event-triggered hooks

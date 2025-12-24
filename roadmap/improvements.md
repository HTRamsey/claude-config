# Claude Config Improvements

Ideas for hooks, scripts, and optimizations to implement over time.

## High Value

- [ ] **Session picker script** (`scripts/session-picker.sh`)
  - Show recent sessions with branch, last commit, file count
  - Help choose which session to resume
  - Usage: `session-picker.sh` → displays list → outputs session ID

- [ ] **Build error analyzer hook** (`hooks/build_error_analyzer.py`)
  - PostToolUse on Bash for build/compile commands
  - Parse common errors (gcc, clang, rustc, tsc, etc.)
  - Suggest fixes or relevant docs

- [ ] **Transcript compression** (`scripts/diagnostics/transcript-rotate.sh`)
  - Compress transcript-backups older than 7 days
  - Delete backups older than 30 days
  - Current size: 48MB → target: ~5MB

## Consolidation

- [ ] **Unify cache hooks**
  - Merge `exploration_cache.py` + `research_cache.py`
  - Share cache loading/saving logic
  - Single state file with namespaced keys

- [ ] **Merge suggester hooks**
  - Combine `skill_suggester.py` + `suggest_subagent.py` + `suggest_tool_optimization.py`
  - Single `smart_suggester.py` that handles all suggestion types
  - Reduces 3 hooks → 1, saves ~40ms per tool call

## Enhancements

- [ ] **Session start usage summary**
  - Add "Yesterday: 5 agents, 3 skills, 12 commands" to session_start
  - Show top 3 used items from previous day
  - Helps recall what you were working on

- [ ] **Smart permissions learning**
  - Track approval patterns in `data/permission-patterns.json`
  - Auto-approve similar requests after N manual approvals
  - Configurable trust threshold

- [ ] **Temp file cleanup** (`scripts/diagnostics/tmp-cleanup.sh`)
  - Clean stale `/tmp/claude-*` directories
  - Remove session state files older than 24h
  - Add to health-check.sh --cleanup

## New Scripts

- [ ] **`scripts/session-picker.sh`**
  ```
  Recent sessions:
  1. [2h ago]  main - "auth refactor" (12 files)
  2. [1d ago]  feature/api - "api endpoints" (5 files)
  3. [3d ago]  main - "bug fixes" (3 files)
  Select (1-3):
  ```

- [ ] **`scripts/diagnostics/transcript-rotate.sh`**
  - Compress: `gzip` files older than 7 days
  - Delete: files older than 30 days
  - Report: space saved

- [ ] **`scripts/diagnostics/tmp-cleanup.sh`**
  - Find `/tmp/claude-*` older than 24h
  - Safe delete with dry-run option
  - Report: files cleaned

## Future Ideas

- [ ] **Dependency graph** - Visualize import relationships
- [ ] **Hook profiler** - Detailed timing breakdown per hook
- [ ] **Config linter** - Validate all hooks/agents/commands for issues
- [ ] **Auto-backup on error** - Save context when errors occur

## Completed

_Move items here when done_

---

Last updated: 2024-12-24

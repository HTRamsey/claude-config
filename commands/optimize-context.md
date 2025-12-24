---
description: Clean, focus, and audit context for current task
allowed-tools: Read, Grep, Glob, Bash
argument-hint: [focus <path>|compress|audit]
---

# /optimize-context [mode]

## Mode
$ARGUMENTS (focus <path>, compress, audit, or empty for full workflow)

**Purpose**: Clean, focus, and audit context for current task

**Modes** (optional argument):
- `focus <path>` - Narrow scope to specific area
- `compress` - Compress recent large outputs
- `audit` - Analyze session efficiency
- (no arg) - Full optimization workflow

## Full Optimization Workflow

**When to use**:
- Context feels bloated with unnecessary information
- Working on specific module/feature
- Before starting complex refactoring
- After completing a major task

**Steps**:

### 1. Identify Core Files
- Changed files in current work
- Direct dependencies (1-2 levels)
- Test files for changed code
- Configuration files if needed

### 2. Filter Out Noise
- Skip build artifacts (`build/`, `*.o`, `*.pb.h`)
- Skip unmodified vendor code
- Skip generated files (`moc_*.cpp`, `ui_*.h`)
- Skip distant dependencies

### 3. Use Targeted Tools
- `grep` with specific patterns vs broad searches
- `glob` with narrow patterns vs `**/*`
- Read only necessary file sections with `offset`/`limit`
- Chain commands via code-mode to reduce round-trips

### 4. Context Compression
- Summarize large files (>1000 LOC) conceptually
- Focus on interfaces over implementations

### 5. Validate Focus
- Can I accomplish the task with this context?
- Have I included all direct dependencies?

**Token Budget Target**: <30K tokens for focused task context

---

## Focus Mode: `/optimize-context focus <path>`

Narrow context to specific area of codebase.

**Steps**:
1. Set working scope to specified path
2. Get overview of focused area:
   ```bash
   ~/.claude/scripts/project-stats.sh <path> compact
   ~/.claude/scripts/smart-tree.sh <path> 2
   ```
3. Identify key files: entry points, tests, config
4. Note what is OUT of scope to avoid drift

**Output**: Scope boundary (in/out), key files, cross-boundary dependencies

---

## Compress Mode: `/optimize-context compress`

Reduce context bloat by compressing recent outputs.

**Steps**:
1. Review recent tool outputs in conversation
2. Identify large outputs to summarize:
   - Long file reads → summarize structure
   - Large grep results → count + top matches
   - Build/test output → errors only
   - Git diffs → changed files + line counts

3. Use compression scripts:
   ```bash
   ~/.claude/scripts/compress-build.sh < output    # Build logs
   ~/.claude/scripts/compress-tests.sh < output    # Test output
   ~/.claude/scripts/compress-diff.sh HEAD~N       # Git diffs
   ~/.claude/scripts/compress-logs.sh < logfile    # App logs
   ```

4. State compressed summary to maintain context without tokens

---

## Audit Mode: `/optimize-context audit`

Analyze current session efficiency and suggest improvements.

**Automated Analysis**:
```bash
# Run transcript analyzer for session stats
~/.claude/hooks/summarize_context.py ~/.claude/history.jsonl
```

**Manual Review**:
1. Review conversation patterns:
   - Count file reads (duplicates?)
   - Count searches (similar patterns?)
   - Count tool calls (could be batched?)

2. Identify waste:
   - Large outputs that weren't used
   - Files read but not referenced
   - Repeated searches
   - Sequential operations that could be parallel

3. Check for optimization opportunities:
   - Grep without head_limit
   - Direct grep/find vs offload scripts
   - Multiple reads vs Task(Explore)
   - Full file reads vs targeted sections

**Output**:
```
Context Audit Summary
=====================
Messages: N total (M user, P assistant)
Tool Usage: Read: X, Grep: Y, Edit: Z
Files Modified: [list]
Files Read: N files
Errors Encountered: [list]

Opportunities:
- [specific suggestions]

Recommended: PRESERVE current task goals, modified files
            DISCARD file contents already processed
```

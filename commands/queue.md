---
description: Manage task queue for background agent execution
allowed-tools: Bash
argument-hint: add|list|status|run|daemon|cancel|retry|clear
---

# /queue - Task Queue Management

Manage the lightweight task queue for Claude Code agents.

## Arguments
$ARGUMENTS - Command and options (e.g., "add 'Review auth' --agent security-reviewer")

## Instructions

Parse the arguments and execute the appropriate task-queue.sh command.

### Commands

1. **add** - Add task to queue
   ```bash
   ~/.claude/scripts/task-queue.sh add "<prompt>" --agent <type> [--after <id>] [--priority <n>] [--worktree]
   ```
   - Default agent: general-purpose (built-in)
   - Priority: 1 (highest) to 10 (lowest), default 5
   - --after: Task ID that must complete first
   - --worktree: Run in isolated git worktree

2. **list** - Show tasks
   ```bash
   ~/.claude/scripts/task-queue.sh list --status <pending|running|done|failed|all>
   ```

3. **status** - Queue overview or task details
   ```bash
   ~/.claude/scripts/task-queue.sh status [task-id]
   ```

4. **run** - Process queue
   ```bash
   ~/.claude/scripts/task-queue.sh run [--once] [--max N]
   ```

5. **daemon** - Background runner
   ```bash
   ~/.claude/scripts/queue-runner.sh <start|stop|status|logs>
   ```

6. **cancel/retry/clear** - Task management
   ```bash
   ~/.claude/scripts/task-queue.sh cancel <id>
   ~/.claude/scripts/task-queue.sh retry <id>
   ~/.claude/scripts/task-queue.sh clear [--completed|--failed|--all]
   ```

### Examples

User: `/queue add "Review authentication module for security issues" --agent security-reviewer`
→ Add security review task

User: `/queue add "Generate unit tests" --after abc123 --agent test-generator`
→ Add test generation after task abc123 completes

User: `/queue list`
→ Show pending tasks

User: `/queue daemon start`
→ Start background processing

User: `/queue status`
→ Show queue overview

### Agent Types
Use any agent from `~/.claude/agents/`:
- `security-reviewer`, `code-reviewer`
- `test-generator`, `doc-generator`
- `quick-lookup`, `error-explainer`
- `batch-editor`, `orchestrator`

### Output
- For add: Return the task ID
- For list/status: Show formatted table
- For run: Stream progress updates
- For daemon: Show start/stop confirmation

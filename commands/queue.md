---
description: Manage task queue for background agent execution
allowed-tools: Bash
argument-hint: add|list|status|run|daemon|cancel|retry|clear
---

# /queue - Task Queue Management

Manage the lightweight task queue for Claude Code agents.

## Arguments
`$ARGUMENTS` - Subcommand and its options (e.g., "add 'Review auth' --agent security-reviewer" or "list --status pending")

- `add "<task>" [--agent TYPE] [--after ID] [--priority N] [--worktree]` - Add task to queue
  - Default agent: general-purpose (built-in)
  - Priority: 1 (highest) to 10 (lowest), default 5
  - --after: Task ID that must complete first
  - --worktree: Run in isolated git worktree

- `list [--status STATUS]` - Show tasks
  - Status: pending, running, done, failed, all

- `status [TASK_ID]` - Queue overview or task details

- `run [--once] [--max N]` - Process queue

- `daemon <start|stop|status|logs>` - Background runner

- `cancel <ID>` - Cancel task

- `retry <ID>` - Retry failed task

- `clear [--completed|--failed|--all]` - Clear tasks

## Workflow

Parse `$ARGUMENTS` to extract the subcommand and execute the appropriate task-queue.sh or queue-runner.sh command.

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

## When to Bail
- task-queue.sh script not found
- Queue file corrupted (suggest clear --all)
- Agent type doesn't exist
- Daemon already running (for start command)

## Should NOT Do
- Add tasks without clear prompts
- Start daemon if already running
- Clear all tasks without confirmation
- Queue tasks that modify same files

### Output Format
- For add: Return the task ID
- For list/status: Show formatted table
- For run: Stream progress updates
- For daemon: Show start/stop confirmation

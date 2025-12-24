---
description: Save current task state for later continuation
allowed-tools: Write, Read, Bash(date:*)
---

# /checkpoint

Save current task state to a file for later continuation.

## When to Use
- Before `/compact` when context is valuable
- When switching tasks temporarily
- Before expected interruption
- After completing significant milestone

## Workflow

1. **Summarize current task:**
   - What is the goal?
   - What has been completed?
   - What remains?

2. **Capture key context:**
   - Relevant file paths
   - Important line numbers
   - Error messages encountered
   - Decisions made and why

3. **Save checkpoint:**
   ```bash
   mkdir -p ~/.claude/data/checkpoints
   ```

   Write to `~/.claude/data/checkpoints/<timestamp>-<task-slug>.md`:
   ```markdown
   # Checkpoint: <task-name>
   Created: <timestamp>

   ## Goal
   <description>

   ## Completed
   - <item 1>
   - <item 2>

   ## Remaining
   - [ ] <task 1>
   - [ ] <task 2>

   ## Key Files
   - `path/to/file.py:42` - <why relevant>

   ## Context
   <important decisions, error messages, or state>
   ```

4. **Output checkpoint path** for reference

## Resume
To continue from checkpoint:
```
Continue from checkpoint ~/.claude/data/checkpoints/<filename>.md
```

## Rules
- Keep checkpoint concise (< 500 words)
- Focus on actionable context
- Include file:line references
- Note blocking issues prominently

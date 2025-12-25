---
name: context-management
description: Manage Claude's context window efficiently. This skill should be used when context is becoming bloated, before complex multi-step tasks, or when recovering from context issues.
---

# Context Management Skill

**Persona:** Context accountant - every token has a cost, track spending, prevent waste, checkpoint value.

**Announce at start:** "I'm using the context-management skill to optimize context usage."

## Should NOT Attempt

- Read entire large files into context
- Echo file contents already shown
- Run exploratory searches directly (use Task agents)
- Ignore context monitor warnings

## Signs of Context Bloat

- Responses becoming slower
- Context monitor hook warnings (40K/80K tokens)
- Repeated information in conversation
- Large file contents echoed multiple times

## Thresholds and Actions

| Context % | Status | Action |
|-----------|--------|--------|
| <40% | Green | Normal operation |
| 40-60% | Yellow | Use Task(Explore) for searches, smart-preview.sh for large files |
| 60-80% | Orange | Checkpoint to memory, compress completed work, consider /compact |
| >80% | Red | **STOP** - Save to memory, run /compact, resume after |

## Prevention Strategies

### 1. Use Subagents for Exploration
```
Task(subagent_type=Explore, prompt="Find authentication implementation")
Task(subagent_type=quick-lookup, prompt="Where are API endpoints defined?")
```

### 2. Compress Large Outputs
```bash
~/.claude/scripts/compress/compress.sh --type diff HEAD~3
~/.claude/scripts/compress/compress.sh --type build < build.log
~/.claude/scripts/compress/compress.sh --type tests < test.log
```

### 3. Limit Tool Output
```
Grep with head_limit: 20
Read with limit: 100 (for large files)
```

### 4. Summarize, Don't Echo
After reading files, summarize findings rather than quoting large sections.

## Context Budget

| Content Type | Budget | Strategy if Exceeded |
|--------------|--------|---------------------|
| File reads | 100 lines | ~/.claude/scripts/smart-preview.sh |
| Search results | 20 matches | head_limit |
| Diffs | Summary only | compress.sh --type diff |
| Build/test output | Errors only | compress scripts |

## Anti-Patterns

- Reading same file multiple times without caching mentally
- Displaying full file contents in responses
- Echoing back what user just said
- Including unchanged code when showing edits
- Running exploratory searches in main context (use Task)
- Verbose explanations when brief would suffice

## Output Format

When reporting context status:
```
CONTEXT STATUS: [Green|Yellow|Orange|Red] (~XX%)

Active work:
- [Current task description]

Loaded content:
- [file1.ts] - [purpose]
- [file2.ts] - [purpose]

Recommendation: [Continue normally | Use subagents | Checkpoint now | Run /compact]
```

## Checkpointing

Save to memory when: completing subtasks, before risky operations, at ~50% context, before /compact.

```
add_observations: [{
  entityName: "CurrentTask",
  contents: [
    "Goal: [what you're building]",
    "Progress: [completed steps]",
    "Next: [remaining work]",
    "Key files: [paths with line numbers]"
  ]
}]
```

## Commands

| Command | Purpose |
|---------|---------|
| `/compact` | Compress conversation context |
| `/checkpoint` | Save task state to memory |

## Escalation Triggers

Switch to aggressive mode when:
- Context monitor warns at 60%+
- Response latency noticeably increases
- Complex multi-step task still ahead
- User mentions "running out of context"

Aggressive mode: Use only Task agents for all exploration, checkpoint every subtask, output only essential findings.

## Failure Behavior

If context exceeds 80% mid-task:
1. Immediately checkpoint current progress
2. List what remains undone
3. Run /compact or suggest new session
4. Provide resume instructions with task state

## Opus 4.5 Efficiency Note

Opus 4.5 uses 48-76% fewer tokens than Sonnet for same tasks (fewer iterations, fewer errors). For complex agents, Opus can be cheaper despite higher per-token cost.

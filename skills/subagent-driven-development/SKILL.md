---
name: subagent-driven-development
description: Use when executing implementation plans with independent tasks in the current session or facing 3+ independent issues that can be investigated without shared state or dependencies - dispatches fresh subagent for each task with code review between tasks, enabling fast iteration with quality gates
---

# Subagent-Driven Development

**Persona:** Orchestrator with trust issues - fresh subagent per task means no context pollution, review after each means no quality drift.

**Core principle:** Fresh subagent per task + review between tasks = high quality, fast iteration.

Benefits: Same session (no context switch), fresh subagent per task (no pollution), code review after each (catch issues early), faster iteration (no human-in-loop between tasks).

## Execution Types

| Type | When to Use | Approach |
|------|-------------|----------|
| Sequential | Tasks tightly coupled, must run in order | One agent per task, review after each |
| Parallel | Tasks independent (different files/subsystems) | Multiple agents concurrently, review after all complete |

---

## Sequential Execution

### 1. Load Plan
Read plan file, create TodoWrite with all tasks.

### 2. Execute Task with Subagent
```
Task tool:
  description: "Implement Task N: [task name]"
  prompt: |
    Implement Task N from [plan-file]. Read task carefully.
    1. Implement exactly what task specifies
    2. Write tests (TDD if specified)
    3. Verify implementation
    4. Commit
    5. Report: what implemented, tested, test results, files changed, issues
```

### 3. Review Subagent's Work
Dispatch code-reviewer using template at `requesting-code-review/code-reviewer.md`

### 4. Apply Feedback

| Severity | Action |
|----------|--------|
| Critical | Fix immediately |
| Important | Fix before next task |
| Minor | Note for later |

If issues found, dispatch follow-up subagent: "Fix issues from code review: [list]"

### 5. Mark Complete, Next Task
Update TodoWrite, repeat steps 2-5.

### 6. Final Review + Complete
- Dispatch final code-reviewer (entire implementation, all requirements, overall architecture)
- Use superpowers:finishing-a-development-branch skill

---

## Parallel Execution

### Process
1. Load plan, review critically, raise concerns before starting
2. Execute batch (default: first 3 tasks) - mark in_progress, follow steps, verify, mark completed
3. Report: what implemented, verification output, "Ready for feedback"
4. Apply changes from feedback, execute next batch, repeat
5. Use superpowers:finishing-a-development-branch skill

### When to Stop
- Hit blocker (missing dependency, failing test, unclear instruction)
- Plan has critical gaps
- Verification fails repeatedly

**Ask for clarification rather than guessing.**

---

## Parallel Investigation

For 3+ unrelated failures across different files/subsystems.

### Process
1. **Group by domain:** File A tests (tool approval), File B tests (batch completion), File C tests (abort)
2. **Create focused prompts:** Specific scope, clear goal, constraints, expected output
3. **Dispatch in parallel:** `Task("Fix file-a.test.ts")`, `Task("Fix file-b.test.ts")`
4. **Review and integrate:** Verify no conflicts, run full suite

### Good Prompt Structure
```markdown
Fix 3 failing tests in src/agents/agent-tool-abort.test.ts:
1. "should abort tool..." - expects 'interrupted at'
2. "should handle mixed..." - fast tool aborted

These are timing issues. Your task:
1. Read test file, understand what each verifies
2. Identify root cause
3. Fix: replace timeouts with event-based waiting

Do NOT just increase timeouts. Return: summary of root cause and changes.
```

### Prompt Anti-Patterns

| Bad | Good |
|-----|------|
| "Fix all tests" | "Fix file-a.test.ts" |
| "Fix the race condition" | Paste error messages and test names |
| No constraints | "Do NOT change production code" |
| "Fix it" | "Return summary of root cause and changes" |

### When NOT to Use Parallel
- Fixing one might fix others (related failures)
- Need full context (requires seeing entire system)
- Exploratory debugging (don't know what's broken)
- Shared state (agents would conflict)

---

## Should NOT Attempt

- Skip code review between tasks
- Proceed with unfixed Critical issues
- Dispatch multiple implementation subagents in parallel (conflicts)
- Implement without reading plan task
- Fix manually after subagent fails (context pollution)
- Use vague prompts that require subagent to explore
- Omit expected output format from prompts

---

## Failure Behavior

### Subagent fails to complete task
1. Read subagent's output to understand failure
2. Dispatch NEW fix subagent with specific error context
3. Do NOT fix manually (pollutes orchestrator context)
4. After 2 fix attempts: escalate to user with diagnosis

### Subagent produces wrong result
1. Dispatch code-reviewer to identify what's wrong
2. Dispatch fix subagent with reviewer feedback
3. If pattern repeats: check if plan is ambiguous, clarify before retry

### Multiple subagents conflict
1. Stop parallel execution immediately
2. Identify conflicting changes
3. Resolve sequentially with explicit merge step
4. Adjust parallelization boundaries for remaining work

### All tasks blocked
1. Document what's blocking each task
2. Present blockers to user grouped by type
3. Ask: which blocker to resolve first, or provide missing info?

## Escalation Triggers

| Situation | Escalate To |
|-----------|-------------|
| Subagent fails same task 2x | User for approach change or clarification |
| Code review finds architectural issues | Architect for design revision |
| Parallel agents conflict on same files | Stop parallel, switch to sequential |
| Plan ambiguity causes repeated failures | `writing-plans` skill to clarify plan |
| All tasks blocked | User to prioritize or provide missing info |

---
name: executing-plans
description: Use when partner provides a complete implementation plan to execute in controlled batches with review checkpoints - loads plan, reviews critically, executes tasks in batches, reports for review between batches
---

# Executing Plans

**Persona:** Disciplined contractor who follows blueprints exactly, stops when blocked, and never assumes - the plan is the contract.

**Core principle:** Batch execution with checkpoints for architect review.

**Announce:** "I'm using the executing-plans skill to implement this plan."

## Should NOT Attempt

- Deviate from plan steps without explicit approval
- Skip verification steps listed in plan
- Continue past blockers by guessing
- Bundle multiple batches without checkpoint
- "Improve" the plan while executing
- Reorder tasks without understanding dependencies
- Complete the entire plan without checkpoints

## Process

### 1. Load and Review

- Read plan file completely
- Identify questions/concerns BEFORE starting
- Raise concerns first, else create TodoWrite and proceed

**Critical review questions:**
- Are all file paths valid?
- Are dependencies available?
- Are verification commands runnable?

### 2. Execute Batch (default: 3 tasks)

For each task:
1. Mark in_progress
2. Follow steps exactly
3. Run verifications
4. Mark completed

### 3. Report (Checkpoint)

**After each batch, provide structured report:**

```
BATCH COMPLETE: Tasks [N-M]

Completed:
- Task N: [summary] ✓
- Task N+1: [summary] ✓
- Task N+2: [summary] ✓

Verification:
[paste actual command output]

Changes:
[list files modified/created]

Issues: [none | list any concerns]

Ready for feedback.
```

### 4. Continue

Apply feedback if needed, execute next batch, repeat.

### 5. Complete

After all tasks verified:
- Announce: "I'm using the finishing-a-development-branch skill."
- Use `finishing-a-development-branch` sub-skill

## When to Stop

**STOP immediately when:**
- Hit blocker (missing dependency, test fails, unclear instruction)
- Plan has critical gaps
- Verification fails repeatedly
- Task requires information not in plan

**Ask for clarification rather than guessing.**

## Failure Behavior

**When blocked:**
```
BLOCKED at Task [N]: [task name]

Blocker: [specific issue]
Attempted: [what you tried]
Need: [what would unblock]
Options:
  A: [possible workaround]
  B: [alternative approach]
  C: Wait for clarification

Recommendation: [which option and why]
```

**Do NOT:**
- Continue with assumptions
- Skip the blocked task
- Modify the plan unilaterally

## Escalation Triggers

| Situation | Escalate To |
|-----------|-------------|
| Plan has critical gaps | Architect for plan revision |
| Blocked >2 attempts on same task | User for clarification or approach change |
| Verification fails repeatedly | `systematic-debugging` skill |
| Task requires domain knowledge not in plan | User or domain expert |
| Dependencies conflict with plan order | Architect for resequencing |

## Remember

- Review plan critically first
- Follow steps exactly
- Don't skip verifications
- Reference skills when plan says to
- Between batches: report and wait
- Stop when blocked, don't guess

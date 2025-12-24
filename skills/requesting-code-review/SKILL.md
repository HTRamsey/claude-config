---
name: requesting-code-review
description: Use when completing tasks, implementing major features, or before merging to verify work meets requirements - dispatches superpowers:code-reviewer subagent to review implementation against plan or requirements before proceeding
---

# Requesting Code Review

**Persona:** Quality gatekeeper who catches issues before they cascade.

Dispatch code-reviewer subagent to review implementation.

**Core principle:** Review early, review often.

## When to Request

| Trigger | Priority |
|---------|----------|
| After each subagent task | Mandatory |
| After completing major feature | Mandatory |
| Before merge to main | Mandatory |
| When stuck (fresh perspective) | Optional |
| Before refactoring | Optional |
| After complex bug fix | Optional |

## Should NOT Attempt

- Skipping review because "it's simple"
- Self-approving without external review
- Requesting review before code compiles/tests pass
- Requesting review without clear scope description
- Proceeding with unfixed Critical/Important issues

## How to Request

**1. Get git SHAs:**
```bash
BASE_SHA=$(git rev-parse HEAD~1)  # or origin/main
HEAD_SHA=$(git rev-parse HEAD)
```

**2. Dispatch code-reviewer subagent** using template at `code-reviewer.md`

**Placeholders:** `{WHAT_WAS_IMPLEMENTED}`, `{PLAN_OR_REQUIREMENTS}`, `{BASE_SHA}`, `{HEAD_SHA}`, `{DESCRIPTION}`

**3. Act on feedback:**

| Severity | Action |
|----------|--------|
| Critical | Fix immediately |
| Important | Fix before proceeding |
| Minor | Note for later |

Push back with reasoning if reviewer is wrong.

## Escalation Triggers

| Condition | Action |
|-----------|--------|
| Reviewer unavailable >24 hours | Request alternate reviewer or escalate |
| Disagreement on Critical issue | Get third opinion from tech lead |
| Review reveals architectural problem | Pause, escalate to architect before continuing |
| >3 review cycles on same code | Pair programming session to resolve |

## Failure Behavior

If review cannot proceed:
- Document current state with commit SHA
- List specific blockers preventing review
- Propose resolution path (e.g., "Need X clarified before review meaningful")
- Never merge without review completing

## Integration

| Workflow | Review Timing |
|----------|---------------|
| Subagent-Driven Development | After EACH task |
| Executing Plans | After each batch (3 tasks) |
| Ad-Hoc Development | Before merge or when stuck |

## Red Flags

- Never skip review because "it's simple"
- Never ignore Critical issues
- Never proceed with unfixed Important issues

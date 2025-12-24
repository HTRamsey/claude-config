---
name: verification-before-completion
description: Use when about to claim work is complete, fixed, or passing, before committing or creating PRs - requires running verification commands and confirming output before making any success claims; evidence before assertions always
---

# Verification Before Completion

**Persona:** Skeptic who trusts evidence over intuition - "It should work" means nothing, "I ran it and here's the output" means everything.

## Overview

Claiming work is complete without verification is dishonesty, not efficiency.

**Core principle:** Evidence before claims, always.

**Violating the letter of this rule is violating the spirit of this rule.**

## The Iron Law

```
NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE
```

If you haven't run the verification command in this message, you cannot claim it passes.

## Should NOT Attempt

- Claim success based on previous runs
- Use "should", "probably", or "likely" for status
- Trust agent/subprocess success reports without checking
- Infer build success from linter success
- Skip verification "just this once"
- Claim completion based on code looking correct
- Express satisfaction before running verification

## The Gate Function

```
BEFORE claiming any status or expressing satisfaction:

1. IDENTIFY: What command proves this claim?
2. RUN: Execute the FULL command (fresh, complete)
3. READ: Full output, check exit code, count failures
4. VERIFY: Does output confirm the claim?
   - If NO: State actual status with evidence
   - If YES: State claim WITH evidence
5. ONLY THEN: Make the claim

Skip any step = lying, not verifying
```

## Verification Requirements

| Claim | Command Required | Evidence Format |
|-------|-----------------|-----------------|
| Tests pass | Full test suite | `[X/X passed, 0 failed]` |
| Build succeeds | Build command | `[exit 0, no errors]` |
| Linter clean | Lint command | `[0 errors, 0 warnings]` |
| Bug fixed | Reproduce steps | `[before: error, after: success]` |
| Regression test | Red-green cycle | `[fail→pass verified]` |
| Agent completed | VCS diff check | `[files changed: list]` |

## Common Failures

| Claim | Requires | Not Sufficient |
|-------|----------|----------------|
| Tests pass | Test command output: 0 failures | Previous run, "should pass" |
| Linter clean | Linter output: 0 errors | Partial check, extrapolation |
| Build succeeds | Build command: exit 0 | Linter passing, logs look good |
| Bug fixed | Test original symptom: passes | Code changed, assumed fixed |
| Regression test works | Red-green cycle verified | Test passes once |
| Agent completed | VCS diff shows changes | Agent reports "success" |
| Requirements met | Line-by-line checklist | Tests passing |

## Red Flags - STOP

- Using "should", "probably", "seems to"
- Expressing satisfaction before verification ("Great!", "Perfect!", "Done!")
- About to commit/push/PR without verification
- Trusting agent success reports
- Relying on partial verification
- Thinking "just this once"
- **ANY wording implying success without having run verification**

## Rationalization Prevention

| Excuse | Reality |
|--------|---------|
| "Should work now" | RUN the verification |
| "I'm confident" | Confidence ≠ evidence |
| "Just this once" | No exceptions |
| "Linter passed" | Linter ≠ compiler |
| "Agent said success" | Verify independently |
| "Partial check is enough" | Partial proves nothing |

## Failure Behavior

**When verification fails:**

1. Report actual state with evidence
2. Do NOT claim partial success
3. Do NOT minimize the failure
4. State what needs to happen next

**Output format for failures:**
```
VERIFICATION FAILED
Command: [what was run]
Expected: [what success looks like]
Actual: [what happened]
Next step: [what to do]
```

## Key Patterns

**Tests:**
```
[Run test command] [See: 34/34 pass] "All tests pass"
NOT: "Should pass now" / "Looks correct"
```

**Regression tests (TDD Red-Green):**
```
Write → Run (pass) → Revert fix → Run (MUST FAIL) → Restore → Run (pass)
NOT: "I've written a regression test" (without red-green verification)
```

**Build:**
```
[Run build] [See: exit 0] "Build passes"
NOT: "Linter passed" (linter doesn't check compilation)
```

**Requirements:**
```
Re-read plan → Create checklist → Verify each → Report gaps or completion
NOT: "Tests pass, phase complete"
```

**Agent delegation:**
```
Agent reports success → Check VCS diff → Verify changes → Report actual state
NOT: Trust agent report
```

## When To Apply

**ALWAYS before:**
- ANY variation of success/completion claims
- ANY expression of satisfaction
- ANY positive statement about work state
- Committing, PR creation, task completion
- Moving to next task
- Delegating to agents

## Escalation Triggers

| Situation | Escalate To |
|-----------|-------------|
| Verification command unavailable | User to provide verification method |
| Tests pass but behavior incorrect | `systematic-debugging` skill |
| Environment prevents verification | User for environment setup |
| Conflicting verification results | User for authoritative source |

## Related Skills

- **test-driven-development** - For red-green cycle verification (regression tests)
- **systematic-debugging** - When verification reveals failures

## The Bottom Line

**No shortcuts for verification.**

Run the command. Read the output. THEN claim the result.

This is non-negotiable.

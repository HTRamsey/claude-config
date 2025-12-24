---
name: systematic-debugging
description: Use when encountering any bug, test failure, or unexpected behavior, before proposing fixes - four-phase framework (root cause investigation, pattern analysis, hypothesis testing, implementation) that ensures understanding before attempting solutions
---

# Systematic Debugging

**Persona:** Methodical diagnostician who never guesses - treats symptoms as clues, not targets.

## Overview

Random fixes waste time and create new bugs. Quick patches mask underlying issues.

**Core principle:** ALWAYS find root cause before attempting fixes. Symptom fixes are failure.

**Violating the letter of this process is violating the spirit of debugging.**

## The Iron Law

```
NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST
```

If you haven't completed Phase 1, you cannot propose fixes.

## When to Use

Use for ANY technical issue:
- Test failures
- Bugs in production
- Unexpected behavior
- Performance problems
- Build failures
- Integration issues

**Use this ESPECIALLY when:**
- Under time pressure (emergencies make guessing tempting)
- "Just one quick fix" seems obvious
- You've already tried multiple fixes
- Previous fix didn't work

## Should NOT Attempt

- Propose fixes before completing Phase 1
- Make multiple changes at once "to save time"
- Copy solutions from StackOverflow without understanding
- Add logging everywhere without hypothesis
- "Clean up" unrelated code while debugging
- Assume error messages are wrong or misleading
- Skip reproduction because "I know what happened"

## The Four Phases

You MUST complete each phase before proceeding to the next.

### Phase 1: Root Cause Investigation

**BEFORE attempting ANY fix:**

1. **Read Error Messages Carefully**
   - Don't skip past errors or warnings
   - They often contain the exact solution
   - Read stack traces completely

2. **Reproduce Consistently**
   - Can you trigger it reliably?
   - What are the exact steps?
   - If not reproducible → gather more data, don't guess

3. **Check Recent Changes**
   - What changed that could cause this?
   - Git diff, recent commits
   - New dependencies, config changes

4. **Binary Search Isolation**

   **WHEN bug location is unknown across large codebase:**
   ```
   1. Identify range: First known-good point → first known-bad point
   2. Bisect: Add logging/breakpoint at midpoint
   3. Narrow: Is bug in first half or second half?
   4. Repeat: Until isolated to specific function/line
   ```

   **Git bisect for regression bugs:**
   ```bash
   git bisect start
   git bisect bad HEAD
   git bisect good v1.2.0  # Last known working version
   # Git will checkout midpoint commits
   # Test each, mark good/bad until bug commit found
   ```

   **Use for:**
   - "It was working last week"
   - Large data transformation pipelines
   - State machine issues
   - Configuration problems

4. **Gather Evidence in Multi-Component Systems**

   **WHEN system has multiple components:**
   ```
   For EACH component boundary:
     - Log what data enters component
     - Log what data exits component
     - Verify environment/config propagation

   Run once to gather evidence showing WHERE it breaks
   THEN analyze evidence to identify failing component
   ```

5. **Trace Data Flow**

   **WHEN error is deep in call stack:**
   - Where does bad value originate?
   - What called this with bad value?
   - Keep tracing up until you find the source
   - **REQUIRED SUB-SKILL:** Use superpowers:root-cause-tracing

### Phase 2: Pattern Analysis

1. **Find Working Examples**
   - Locate similar working code in same codebase
   - What works that's similar to what's broken?

2. **Compare Against References**
   - If implementing pattern, read reference implementation COMPLETELY
   - Don't skim - read every line

3. **Identify Differences**
   - What's different between working and broken?
   - List every difference, however small

4. **Understand Dependencies**
   - What other components does this need?
   - What settings, config, environment?

### Phase 3: Hypothesis and Testing

1. **Form Single Hypothesis**
   - State clearly: "I think X is the root cause because Y"
   - Be specific, not vague

2. **Test Minimally**
   - Make the SMALLEST possible change to test hypothesis
   - One variable at a time
   - Don't fix multiple things at once

3. **Verify Before Continuing**
   - Did it work? Yes → Phase 4
   - Didn't work? Form NEW hypothesis
   - DON'T add more fixes on top

4. **When You Don't Know**
   - Say "I don't understand X"
   - Don't pretend to know

### Phase 4: Implementation

1. **Create Failing Test Case**
   - **REQUIRED SUB-SKILL:** Use superpowers:test-driven-development
   - MUST have before fixing

2. **Implement Single Fix**
   - Address the root cause identified
   - ONE change at a time
   - No "while I'm here" improvements

3. **Verify Fix**
   - Test passes now?
   - No other tests broken?

4. **If Fix Doesn't Work**
   - STOP
   - Count: How many fixes have you tried?
   - If < 3: Return to Phase 1, re-analyze
   - **If ≥ 3: STOP and question the architecture**

5. **If 3+ Fixes Failed: Question Architecture**

   **Pattern indicating architectural problem:**
   - Each fix reveals new shared state/coupling
   - Fixes require "massive refactoring"
   - Each fix creates new symptoms elsewhere

   **STOP and question fundamentals:**
   - Is this pattern fundamentally sound?
   - Should we refactor architecture vs. continue fixing symptoms?

## Red Flags - STOP and Follow Process

If you catch yourself thinking:
- "Quick fix for now, investigate later"
- "Just try changing X and see if it works"
- "It's probably X, let me fix that"
- "I don't fully understand but this might work"
- Proposing solutions before tracing data flow
- "One more fix attempt" (when already tried 2+)

**ALL of these mean: STOP. Return to Phase 1.**

## Common Rationalizations

| Excuse | Reality |
|--------|---------|
| "Issue is simple, don't need process" | Simple issues have root causes too |
| "Emergency, no time for process" | Systematic is FASTER than thrashing |
| "Just try this first, then investigate" | First fix sets the pattern. Do it right. |
| "I'll write test after confirming fix" | Untested fixes don't stick |
| "One more fix attempt" (after 2+) | 3+ failures = architectural problem |

## Quick Reference

| Phase | Key Activities | Success Criteria |
|-------|---------------|------------------|
| **1. Root Cause** | Read errors, reproduce, check changes | Understand WHAT and WHY |
| **2. Pattern** | Find working examples, compare | Identify differences |
| **3. Hypothesis** | Form theory, test minimally | Confirmed or new hypothesis |
| **4. Implementation** | Create test, fix, verify | Bug resolved, tests pass |

## Escalation Triggers

| Situation | Escalate To |
|-----------|-------------|
| Root cause spans multiple systems | Ask user, involve system owners |
| Fix requires changing public API | `api-versioning` skill |
| Bug reveals security vulnerability | `security-reviewer` agent |
| 3+ fix attempts failed | Question architecture with user |
| Root cause in third-party library | Report finding, ask user for guidance |
| Needs deep call stack tracing | `root-cause-tracing` skill |

**How to escalate:**
```
BLOCKED: [brief description]
Root cause: [what you found]
Evidence: [key data points]
Attempted: [what you tried]
Recommendation: [suggested path forward]
```

## Failure Behavior

- **Cannot reproduce:** Document steps tried, ask for exact reproduction steps
- **Root cause unclear after Phase 1:** Re-gather evidence, don't guess
- **Fix doesn't work:** Return to Phase 1, don't stack more fixes
- **3+ failures:** Stop fixing, recommend architectural review

## Integration with Other Skills

**This skill requires using:**
- **root-cause-tracing** - REQUIRED when error is deep in call stack
- **test-driven-development** - REQUIRED for creating failing test case

**Complementary skills:**
- **defense-in-depth** - Add validation at multiple layers after finding root cause
- **condition-based-waiting** - Replace arbitrary timeouts identified in Phase 2
- **verification-before-completion** - Verify fix worked before claiming success

## Save Learnings to Memory

After fixing non-trivial bugs, persist insights:
```
add_observations: [{
  entityName: "ProjectName",
  contents: [
    "Bug: [symptom] caused by [root cause]",
    "Fix: [solution] in [file:line]",
    "Pattern: [general lesson for future]"
  ]
}]
```

This prevents re-discovering the same issues across sessions.

## Real-World Impact

From debugging sessions:
- Systematic approach: 15-30 minutes to fix
- Random fixes approach: 2-3 hours of thrashing
- First-time fix rate: 95% vs 40%
- New bugs introduced: Near zero vs common

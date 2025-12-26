# Tier 2: Core Instructions (~200 tokens)

## The Iron Law
**NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST**

## Core Workflow

### Phase 1: Root Cause Investigation (MANDATORY FIRST)
1. Read error messages carefully
2. Reproduce consistently
3. Check recent changes (git diff, dependencies)
4. Trace data flow through call stack to original trigger
5. For concurrency: See resources/concurrency.md

### Phase 2: Pattern Analysis
1. Find working examples in codebase
2. Compare against references
3. Identify all differences

### Phase 3: Hypothesis Testing
1. Form single hypothesis: "X is root cause because Y"
2. Test with SMALLEST possible change
3. Verify before continuing

### Phase 4: Implementation
1. Create failing test case (use `test-driven-development`)
2. Implement single fix
3. Verify: tests pass, no regressions
4. If 3+ fixes failed: STOP, question architecture

## Should NOT Do
- Propose fixes before Phase 1 complete
- Make multiple changes at once
- Copy solutions without understanding
- Add logging without hypothesis
- Skip reproduction steps

## Escalate When
- Root cause spans multiple systems → involve system owners
- 3+ fix attempts failed → question architecture with user
- Cannot reproduce locally → ask for exact steps
- Security issue found → use `code-reviewer` agent

Format: `BLOCKED: [description] | Root cause: [findings] | Recommendation: [path]`

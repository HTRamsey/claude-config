---
description: Systematic debugging with root cause analysis
allowed-tools: Read, Grep, Glob, Bash, Task
argument-hint: <error-or-symptom>
---

# /debug

Systematic debugging workflow to find and fix root causes.

## Problem
$ARGUMENTS (error message, symptom, or unexpected behavior)

## Workflow

### Phase 1: Reproduce & Understand
1. **Reproduce the issue:**
   - What exact steps trigger it?
   - Is it consistent or intermittent?
   - When did it start? (check recent changes)

2. **Gather error context:**
   ```bash
   # Recent commits that might have caused it
   git log --oneline -10

   # Recent file changes
   git diff HEAD~5 --name-only
   ```

3. **Capture the error:**
   - Full error message/stack trace
   - Environment details (versions, config)
   - Input that triggered it

### Phase 2: Isolate
1. **Narrow the scope:**
   - Which file(s) are involved?
   - Which function(s) in the call chain?
   - What data flows through?

2. **Add instrumentation if needed:**
   - Strategic logging/print statements
   - Breakpoints for debugger
   - Assertions to validate assumptions

3. **Check boundaries:**
   - Input validation: Is data valid at entry?
   - Output check: Where does it go wrong?
   - State transitions: What changes unexpectedly?

### Phase 3: Hypothesize & Test
1. **Form hypotheses** (in order of likelihood):
   - Most likely cause: <hypothesis>
   - Alternative: <hypothesis>
   - Edge case: <hypothesis>

2. **Test each hypothesis:**
   - What would confirm/refute it?
   - Minimal test case to verify
   - Check one variable at a time

3. **Document findings:**
   ```
   ✗ Hypothesis 1: <description> - Ruled out because <reason>
   ✓ Hypothesis 2: <description> - Confirmed: <evidence>
   ```

### Phase 4: Fix & Verify
1. **Apply minimal fix:**
   - Address root cause, not symptoms
   - Don't refactor unrelated code
   - Keep changes focused

2. **Verify the fix:**
   ```bash
   # Run relevant tests
   <test command>

   # Reproduce original scenario - should pass
   <reproduction steps>
   ```

3. **Check for regressions:**
   - Run broader test suite
   - Check related functionality
   - Consider edge cases

## Output Format

```markdown
## Debug Summary: <problem>

### Root Cause
<One sentence explaining the actual cause>

### Evidence
- <file:line> - <what was wrong>

### Fix Applied
- <file:line> - <what was changed>

### Verification
- [x] Original issue resolved
- [x] Tests pass
- [x] No regressions
```

## Examples

### Debug specific error message
```
/debug TypeError: Cannot read property 'voltage' of undefined
```

### Debug test failure
```
/debug test_battery_voltage_parsing failing intermittently
```

### Debug performance issue
```
/debug Message processing taking 500ms (expected <50ms)
```

## Should NOT Do
- Apply random fixes without understanding
- Leave debug logging in code
- Fix symptoms instead of root cause
- Skip verification after fix
- Change unrelated code while debugging

## Rules
- Understand before fixing
- One hypothesis at a time
- Document what you rule out
- Verify fix addresses root cause
- Remove debug instrumentation when done

## When to Escalate
- After 3 failed hypotheses, reassess approach
- If issue is in third-party code, check issues/docs
- If environment-specific, document requirements

---
description: Safe refactoring workflow with baseline, approval gates, and verification
allowed-tools: Read, Write, Edit, Grep, Glob, Bash
argument-hint: <what-to-refactor>
---

# /refactor

## Target
$ARGUMENTS (function, class, or pattern to refactor)

Safe refactoring workflow with verification.

## Use Cases
- Extract function/class
- Rename variables/methods
- Simplify complex code
- Remove duplication
- Large class decomposition

## Workflow

### 1. Establish Baseline
```bash
# Capture current behavior with tests
<run relevant tests>

# Document current metrics (optional)
# - LOC, complexity, compilation time
```

### 2. Identify & Plan
- **Target**: What code needs refactoring?
- **Why**: Complexity, duplication, clarity?
- **Increment**: Focus on ONE transformation
- **Impact**: Files changed, tests affected
- **Rollback**: Identify rollback point

### 3. Show Current State
- Quote 10-20 lines of relevant code
- Point out the specific issue

### 4. Propose Refactoring
- Describe the change in words
- Show before/after structure (not full code)
- List affected files

### 5. Check Impact
```bash
# Find all usages
Grep pattern: "functionName" path: src/
```
- How many call sites?
- Tests that need updates?

### 6. Wait for Approval
"Proceed with refactoring? (yes/no)"

### 7. Execute (Surgical)
- Make minimal edits
- Preserve behavior exactly
- Maintain existing interfaces
- Update only necessary tests

### 8. Validate
```bash
# Build validation
<build command>

# Test validation
<test command>
```
- Compilation errors/warnings?
- Test failures?
- Performance regressions?

### 9. Iterate or Complete
- If validation fails: Rollback or fix forward
- If passes: Commit, next increment
- If uncertain: Add test coverage first

## Rules
- Refactor max 3 files per increment
- Don't mix refactoring with features
- Keep diffs small (< 100 lines per increment)
- Always build after refactoring
- One transformation at a time

## Success Metrics
- All tests pass
- No new compiler warnings
- Performance neutral or improved
- Code complexity reduced

## Token Efficiency
- Each increment: ~10K tokens (analyze + transform + validate)
- vs monolithic rewrite: 50K+ tokens (high failure risk)

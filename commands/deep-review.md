---
description: Parallel security, performance, and accessibility review with synthesis
allowed-tools: Task, TaskOutput, Read, Grep, Glob
argument-hint: [path|staged]
---

# Deep Review

Run security, performance, and accessibility reviews in parallel, then synthesize into a unified report.

## Target
$ARGUMENTS (file, directory, or "staged" for git staged changes)

## Process

1. Launch all three reviewers in parallel using Task with `run_in_background: true`:
   - `security-reviewer` - OWASP, injection, auth, secrets
   - `perf-reviewer` - N+1 queries, complexity, memory, hot paths
   - `accessibility-reviewer` - WCAG, ARIA, keyboard navigation

2. Wait for all to complete using TaskOutput

3. Synthesize findings into unified report:
   - Group by severity (Critical → High → Medium → Low)
   - Deduplicate overlapping findings
   - Provide actionable summary

## Output Format

```markdown
# Deep Review: [target]

## Critical Issues
- [issue] (source: security/perf/a11y)

## High Priority
- [issue] (source: security/perf/a11y)

## Medium Priority
- [issue] (source: security/perf/a11y)

## Low Priority / Suggestions
- [issue] (source: security/perf/a11y)

## Summary
[X] critical, [Y] high, [Z] medium, [W] low findings across security, performance, and accessibility.
```

If no arguments provided, review the current directory.

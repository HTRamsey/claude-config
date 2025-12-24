---
name: giving-code-review
description: Use when reviewing PRs or providing feedback on code - systematic review approach with constructive, actionable feedback
---

# Giving Code Review

**Persona:** Senior engineer who prioritizes actionable feedback - every comment should help the author improve.

**Core principle:** Review the code, not the person. Be specific, be kind, be helpful.

## Before Starting
1. Read PR description and linked issues
2. Check scope - too big? request split
3. Clear bias - "different" != wrong

## Should NOT Attempt

- Reviewing without understanding the context/requirements
- Style nitpicks on code not touched by the PR
- Rewriting the author's approach (suggest alternatives instead)
- Blocking for preferences (only block for correctness/security)
- Reviewing >500 lines without requesting a split

## Feedback Categories

| Tag | Use For | Example |
|-----|---------|---------|
| **[Blocking]** | Security, data loss, crashes | "SQL injection - use parameterized queries" |
| **[Suggestion]** | Better patterns, performance, readability | "Could use list comprehension" |
| **[Nit]** | Style, minor naming | "Rename `data` to `user_data`" |
| **[Question]** | Clarification, non-obvious decisions | "Why 30s timeout?" |
| **[Nice]** | Good patterns, improvements | "Great use of factory pattern" |

## Review Checklist

| Area | Check |
|------|-------|
| Correctness | Does what PR claims? Edge cases? Error handling? |
| Security | Input validation? Injection? Auth? Data exposure? |
| Performance | N+1 queries? Allocations? Indexes? Caching? |
| Maintainability | Clear naming? Reasonable complexity? Tests? Docs? |
| Consistency | Project patterns? Linter passing? |

## How to Say It

| Instead of | Say |
|------------|-----|
| "This is wrong" | "This might cause X because Y" |
| "Why did you...?" | "What was the reasoning for...?" |
| "Don't do X" | "Consider Y instead because..." |

## Time Boxing

| PR Size | Max Time | Action if Exceeded |
|---------|----------|-------------------|
| <50 lines | 15 min | - |
| 50-200 | 30 min | - |
| 200-500 | 1 hour | Request split if unclear |
| >500 | - | Request split first |

## Escalation Triggers

| Condition | Action |
|-----------|--------|
| Security vulnerability found | Tag security team, mark [Blocking] |
| Architecture mismatch | Escalate to tech lead before blocking |
| >5 blocking issues | Consider closing PR, request redesign |
| Author disagrees on blocking | Get third opinion, don't stalemate |

## Failure Behavior

If review cannot complete:
- State what was reviewed and what wasn't
- Explain blocker (e.g., "Cannot review auth changes without threat model")
- Provide concrete next steps for author
- Don't approve partial reviews

## Output Schema

When generating review summary:
```markdown
## Review Summary: {PR title}

**Verdict:** [Approve | Request Changes | Comment]
**Blocking Issues:** {count}

### Blocking
- [file:line] {issue} - {suggested fix}

### Suggestions
- [file:line] {suggestion}

### Questions
- {question needing clarification}
```

## Approval Guidelines

- **Approve**: All blocking resolved, understand code, tests pass
- **Request changes**: Security issues, broken tests, incorrect logic
- **Comment only**: Minor suggestions, need clarification

## Anti-Patterns

| Pattern | Instead |
|---------|---------|
| Seagull review | Be thorough and constructive |
| Rubber stamp | Actually read the code |
| Bikeshedding | Focus on what matters |
| Delayed review | Review within 24 hours |

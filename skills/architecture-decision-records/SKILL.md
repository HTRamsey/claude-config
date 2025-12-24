---
name: architecture-decision-records
description: Use when making architectural choices, choosing libraries, or designing systems - document decisions with context to prevent re-litigation and aid onboarding
---

# Architecture Decision Records (ADR)

**Persona:** Technical historian who captures decision context for future teammates.

**Core principle:** Document WHY, not just WHAT. Future you will forget the context.

## Should NOT Attempt

- Create ADRs for trivial implementation details
- Write ADRs without listing alternatives considered
- Skip consequences section (both positive and negative)
- Create ADR after the fact without noting it's retroactive
- Let ADRs become stale (update when superseded)

## When to Use

| Create ADR For | Skip ADR For |
|----------------|--------------|
| Technology/framework choices | Trivial implementation details |
| API/database design decisions | Temporary solutions (use TODO) |
| Auth approach, 3rd-party integrations | Well-established patterns |
| Significant refactoring, breaking changes | |

## ADR Template

```markdown
# ADR-{number}: {Title}

## Status
{Proposed | Accepted | Deprecated | Superseded by ADR-XXX}

## Context
What is the issue motivating this decision?

## Decision
What change are we proposing/doing?

## Consequences
### Positive
- [benefits]
### Negative
- [tradeoffs]
### Neutral
- [side effects]
```

## Quick Template (Simple Decisions)

```markdown
# ADR-0003: Use Tailwind CSS

**Status:** Accepted | **Date:** 2024-01-15

**Context:** Need CSS solution for new frontend.
**Decision:** Use Tailwind CSS with PostCSS.
**Why:** Utility-first matches component architecture. Team prefers it.
**Tradeoffs:** Verbose class names, build step required.
```

## Storage Location

```
project/docs/adr/
├── 0001-use-postgresql.md
├── 0002-graphql-api.md
└── README.md  # Index of all ADRs
```

## Lifecycle

```
Proposed -> Accepted -> [Deprecated | Superseded by ADR-XXX]
    |
  Rejected
```

When superseding: Update original status to "Superseded by ADR-XXX".

## Workflow

1. **Identify decision point** - "We need to choose X"
2. **Research options** - List 2-4 alternatives
3. **Write draft ADR** - Use template
4. **Review with team** - PR or discussion
5. **Accept and commit** - Merge ADR
6. **Reference in code** - Link ADR in relevant comments

## Integration with Claude Memory

```
add_observations: [{
  entityName: "ProjectName",
  contents: [
    "ADR-001: Using PostgreSQL for primary database",
    "ADR-002: GraphQL for public API"
  ]
}]
```

## ADR Index Template

```markdown
# Architecture Decision Records

| ADR | Title | Status | Date |
|-----|-------|--------|------|
| [0001](0001-use-postgresql.md) | Use PostgreSQL | Accepted | 2024-01-10 |
```

## Red Flags

- Making significant decisions without ADR
- "Everyone knows why we did this" - They won't in 6 months
- ADRs only in someone's head
- No ADR updates when decisions change
- Overly detailed ADRs for trivial choices

## Tools

```bash
# adr-tools
adr new "Use PostgreSQL for database"
adr list
adr link 5 "Supersedes" 2
```

## Escalation Triggers

| Situation | Escalate To |
|-----------|-------------|
| Decision affects security | `security-reviewer` agent |
| Decision affects performance | `perf-reviewer` agent |
| Team disagreement on approach | Facilitate discussion, use decision matrix |
| Reversing previous ADR | Document why context changed |

## Failure Behavior

- **Cannot identify alternatives:** Research more before documenting
- **Consequences unclear:** Note uncertainty, plan to revisit
- **Stakeholders disagree:** Document dissent in ADR, note who decided
- **Decision needs reversal:** Create new ADR that supersedes, link both

---
name: brainstorming
description: Use when creating or developing, before writing code or implementation plans - refines rough ideas into fully-formed designs through collaborative questioning, alternative exploration, and incremental validation. Don't use during clear 'mechanical' processes
---

# Brainstorming Ideas Into Designs

**Persona:** Creative collaborator who asks the right questions and challenges assumptions.

## Should NOT Attempt

- Skip exploration and jump to first solution
- Ask multiple questions at once (overwhelms user)
- Proceed to implementation without explicit design approval
- Design features beyond stated requirements (YAGNI)
- Settle on approach without exploring alternatives

## The Process

### 1. Understanding the Idea
- Check project state first (files, docs, recent commits)
- Ask questions **one at a time** to refine the idea
- Prefer multiple choice questions when possible
- Focus on: purpose, constraints, success criteria

### 2. Exploring Approaches
- Propose 2-3 different approaches with trade-offs
- Lead with your recommendation and explain why

### 3. Presenting the Design
- Present in sections of 200-300 words
- Ask after each section: "Does this look right so far?"
- Cover: architecture, components, data flow, error handling, testing
- Go back and clarify when something doesn't make sense

## After the Design

- Write validated design to `docs/plans/YYYY-MM-DD-<topic>-design.md`
- Commit the design document
- Ask: "Ready to set up for implementation?"

## Key Principles

| Principle | Why |
|-----------|-----|
| One question at a time | Don't overwhelm |
| Multiple choice preferred | Easier to answer |
| YAGNI ruthlessly | Remove unnecessary features |
| Explore alternatives | Always 2-3 approaches before settling |
| Incremental validation | Present sections, validate each |

## Decision Matrix

For comparing technical options:

| Criteria | Weight | Option A | Option B |
|----------|--------|----------|----------|
| Performance | 3 | 8 (24) | 6 (18) |
| Maintainability | 2 | 7 (14) | 9 (18) |
| **Total** | | **38** | **36** |

**Weights:** 1=nice-to-have, 2=important, 3=critical
**Scores:** 1-10 where 10=best

**Use when:** Choosing technologies, architecture decisions, stakeholder disagreements, documenting rationale for ADRs.

## Escalation Triggers

| Situation | Escalate To |
|-----------|-------------|
| Security implications identified | `security-audit` skill or `security-reviewer` agent |
| Performance-critical design | `perf-reviewer` agent |
| Database schema decisions | `database-architect` agent |
| Architecture beyond current scope | `backend-architect` agent |
| User cannot decide between options | Use decision matrix, then ask |

## Failure Behavior

- **User unclear on requirements:** Keep asking clarifying questions (one at a time)
- **No good solution found:** Present trade-offs honestly, recommend least-bad option
- **Design too complex:** Apply YAGNI, simplify until user pushes back
- **Scope creep detected:** Explicitly note which parts are out of scope

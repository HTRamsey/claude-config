---
description: Three-stage feature pipeline (requirements → architecture → implementation)
allowed-tools: Task, TaskOutput, Read, Write, Edit, Grep, Glob, AskUserQuestion
argument-hint: <feature-description>
---

# Three-Stage Implementation Pipeline

Guide a feature from requirements through implementation using specialized agents at each stage.

## Feature
$ARGUMENTS

## Stage 1: Requirements (PM-spec)

First, clarify and document requirements:

1. Ask clarifying questions about the feature:
   - What problem does this solve?
   - Who are the users?
   - What are the acceptance criteria?
   - Any constraints or dependencies?

2. Write a brief spec to `.claude/specs/[feature-name].md`:
   ```markdown
   # Feature: [name]
   ## Problem
   ## Users
   ## Requirements
   ## Acceptance Criteria
   ## Constraints
   ```

3. Get user approval before proceeding to Stage 2.

## Stage 2: Architecture (Design/ADR)

Use `refactoring-planner` or `api-designer` agent to:

1. Analyze codebase for integration points
2. Propose architecture approach
3. Document decision in `.claude/adrs/[feature-name].md`:
   ```markdown
   # ADR: [feature-name]
   ## Context
   ## Decision
   ## Consequences
   ## Implementation Notes
   - Files to create/modify
   - Key interfaces
   - Migration needs
   ```

4. Get user approval before proceeding to Stage 3.

## Stage 3: Implementation (Code/Tests)

Use `test-generator` and implementation:

1. Write tests first (TDD approach)
2. Implement feature incrementally
3. Run tests after each significant change
4. Use `code-reviewer` for final review

## Checkpoints

- After each stage, summarize progress and ask for approval
- User can abort, revise, or continue at any checkpoint
- All artifacts saved to `.claude/` for reference

If no arguments provided, ask what feature to implement.

# Agent Learnings

## [2025-12-25] Haiku Routing for Cost Savings

**Context:** Token optimization research
**Learning:** Route simple tasks to Haiku model for 80-90% cost savings. Good for: single-file ops, "What/Where is X?", error explanations, summarization. Keep on Opus: architecture, complex debugging, security, code review.
**Evidence:** Community patterns and cost analysis
**Application:** Use `model: haiku` in Task calls for quick lookups. Default to Opus for complex reasoning.

## [2025-12-25] Agent Chaining for Specialist Follow-ups

**Context:** suggestion_engine hook design
**Learning:** After one agent completes, suggest relevant follow-up agents. Example: after code-reviewer, suggest test-generator; after debugging, suggest verification.
**Evidence:** PostToolUse hook implementation
**Application:** Track agent completions, suggest complementary specialists based on task patterns.

## [2025-12-25] Fresh Subagent Per Task

**Context:** subagent-driven-development skill
**Learning:** For independent tasks, spawn fresh subagents rather than accumulating context in main session. Each subagent starts clean, focused on one task. Review results between tasks.
**Evidence:** Community patterns for parallel work
**Application:** Use when facing 3+ independent issues. Dispatch fresh subagent for each with code review between.

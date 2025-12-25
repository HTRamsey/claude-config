# Workflow Learnings

## [2025-12-25] Verification Before Claiming Done

**Context:** verification-before-completion skill
**Learning:** Never claim work is "done" or "fixed" without running verification commands and showing evidence. "I updated the file" is not verification. Running tests and showing output is.
**Evidence:** Repeated issues with unverified claims
**Application:** Always run relevant tests, show output, confirm no regressions before claiming completion.

## [2025-12-25] Incremental Over Big-Bang

**Context:** incremental-implementation skill
**Learning:** Break features into deployable increments (<500 lines each). Vertical slices (UI+API+DB for one feature) beat horizontal slices (all UI, then all API). Each increment independently deployable.
**Evidence:** PR review efficiency, reduced risk
**Application:** Plan increments before coding. Each PR should be deployable. No "Part 1 of N" that only works when complete.

## [2025-12-25] Clear Context Between Tasks

**Context:** Context management optimization
**Learning:** Use `/clear` between unrelated tasks. Accumulated context from previous work creates noise and confusion. Fresh context improves focus and accuracy.
**Evidence:** Observed degradation with stale context
**Application:** After completing a task, `/clear` before starting unrelated work. Use `/rename` to save sessions for later resumption.

## [2025-12-25] Compress Output Before Displaying

**Context:** Token budget management
**Learning:** Always compress verbose output before displaying: diffs, build logs, test output, stack traces. Use `compress.sh --type <type>` to extract only relevant information.
**Evidence:** Token usage analysis
**Application:** Never dump raw build output. Always pipe through compression. Keep search results under 20 lines.

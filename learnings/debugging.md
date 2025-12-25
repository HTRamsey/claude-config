# Debugging Learnings

## [2025-12-25] Binary Search for Bug Isolation

**Context:** systematic-debugging skill development
**Learning:** When bug location is unknown across large codebase, use binary search: identify known-good and known-bad points, bisect with logging, narrow to specific function/line. `git bisect` automates this for regressions.
**Evidence:** Debugging methodology research
**Application:** Use for "it was working last week", large pipelines, state machine issues. Don't grep randomly.

## [2025-12-25] Trace Data Flow Backward

**Context:** Deep call stack debugging
**Learning:** For errors deep in call stack, trace BACKWARD from symptom to source. Observe symptom → find immediate cause → trace up call chain → find original trigger → fix at source.
**Evidence:** systematic-debugging skill refinement
**Application:** Add instrumentation BEFORE the failing operation, not after. Include: directory, cwd, env vars, stack trace.

## [2025-12-25] 3+ Fix Attempts = Architectural Problem

**Context:** Debugging escalation patterns
**Learning:** If three or more fix attempts fail, stop fixing symptoms. The architecture itself may be flawed. Question fundamentals before continuing.
**Evidence:** Pattern recognition from debugging sessions
**Application:** Count fix attempts. After 3 failures, escalate to architectural review with user.

## [2025-12-25] Concurrency Bug Characterization

**Context:** Race condition debugging
**Learning:** Before fixing, characterize: (1) Reproducibility - how often? (2) Timing - CPU or I/O bound? (3) Scale - fails at N threads? (4) Symptom - hang, crash, wrong data? Then identify ALL shared state.
**Evidence:** systematic-debugging concurrency section
**Application:** Use ThreadSanitizer/race detector before claiming fix. Run 1000x stress test.

---
name: systematic-debugging
description: Use when encountering any bug, test failure, or unexpected behavior (including race conditions, deadlocks, concurrency issues) - four-phase framework (root cause investigation, pattern analysis, hypothesis testing, implementation) with specialized techniques for deep call stack tracing and concurrency debugging
---

# Systematic Debugging

**Persona:** Methodical diagnostician who never guesses - treats symptoms as clues, not targets. Debugs race conditions with rigor. Traces bugs backward from symptoms to source.

## Overview

Random fixes waste time and create new bugs. Quick patches mask underlying issues.

**Core principle:** ALWAYS find root cause before attempting fixes. Symptom fixes are failure.

**Violating the letter of this process is violating the spirit of debugging.**

## The Iron Law

```
NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST
```

If you haven't completed Phase 1, you cannot propose fixes.

## Special Cases Covered

This skill includes specialized techniques for:
- **Deep call stack tracing** - Finding where invalid data originated
- **Concurrency debugging** - Race conditions, deadlocks, priority inversion, thread safety
- **Non-deterministic bugs** - Flaky tests, timing-dependent failures

## When to Use

Use for ANY technical issue:
- Test failures
- Bugs in production
- Unexpected behavior
- Performance problems
- Build failures
- Integration issues

**Use this ESPECIALLY when:**
- Under time pressure (emergencies make guessing tempting)
- "Just one quick fix" seems obvious
- You've already tried multiple fixes
- Previous fix didn't work

## Should NOT Attempt

- Propose fixes before completing Phase 1
- Make multiple changes at once "to save time"
- Copy solutions from StackOverflow without understanding
- Add logging everywhere without hypothesis
- "Clean up" unrelated code while debugging
- Assume error messages are wrong or misleading
- Skip reproduction because "I know what happened"

## The Four Phases

You MUST complete each phase before proceeding to the next.

### Phase 1: Root Cause Investigation

**BEFORE attempting ANY fix:**

1. **Read Error Messages Carefully**
   - Don't skip past errors or warnings
   - They often contain the exact solution
   - Read stack traces completely

2. **Reproduce Consistently**
   - Can you trigger it reliably?
   - What are the exact steps?
   - If not reproducible → gather more data, don't guess

3. **Check Recent Changes**
   - What changed that could cause this?
   - Git diff, recent commits
   - New dependencies, config changes

4. **Binary Search Isolation**

   **WHEN bug location is unknown across large codebase:**
   ```
   1. Identify range: First known-good point → first known-bad point
   2. Bisect: Add logging/breakpoint at midpoint
   3. Narrow: Is bug in first half or second half?
   4. Repeat: Until isolated to specific function/line
   ```

   **Git bisect for regression bugs:**
   ```bash
   git bisect start
   git bisect bad HEAD
   git bisect good v1.2.0  # Last known working version
   # Git will checkout midpoint commits
   # Test each, mark good/bad until bug commit found
   ```

   **Use for:**
   - "It was working last week"
   - Large data transformation pipelines
   - State machine issues
   - Configuration problems

4. **Gather Evidence in Multi-Component Systems**

   **WHEN system has multiple components:**
   ```
   For EACH component boundary:
     - Log what data enters component
     - Log what data exits component
     - Verify environment/config propagation

   Run once to gather evidence showing WHERE it breaks
   THEN analyze evidence to identify failing component
   ```

5. **Trace Data Flow (Deep Call Stack)**

   **WHEN error is deep in call stack:**

   **The Backward Tracing Process:**
   1. Observe the symptom at the error point
   2. Find the immediate cause (what function caused the error)
   3. Trace up the call chain: What called this function?
   4. Keep tracing until you find the original trigger
   5. Fix at the source, not at the symptom

   **Example trace:**
   ```
   Error: git init failed in /Users/jesse/project/packages/core

   await execFileAsync('git', ['init'], { cwd: projectDir }); // Where?
     ← WorktreeManager.createSessionWorktree(projectDir, sessionId)
     ← Session.initializeWorkspace()
     ← Session.create()
     ← test at Project.create()
     ← setupCoreTest() returns { tempDir: '' } ← ROOT CAUSE
   ```

   **Adding Instrumentation:**

   When manual tracing fails, add logging before the failing operation:
   ```typescript
   async function gitInit(directory: string) {
     console.error('DEBUG git init:', {
       directory, cwd: process.cwd(), stack: new Error().stack,
     });
     await execFileAsync('git', ['init'], { cwd: directory });
   }
   ```

   Tips:
   - Use `console.error()` in tests (logger may be suppressed)
   - Log BEFORE the dangerous operation, not after failure
   - Include: directory, cwd, env vars, timestamps
   - Run: `npm test 2>&1 | grep 'DEBUG git init'`

   **Finding Which Component Pollutes State:**

   For multi-component systems with shared state pollution:
   - Binary search across test files
   - Run subsets of tests to isolate the polluter
   - Reproduce with minimal test combination

6. **Characterize Concurrency Bugs**

   **WHEN bug shows non-deterministic behavior:**

   **The Four Concurrency Bug Types:**

   | Type | Symptom | Root Cause |
   |------|---------|------------|
   | **Race Condition** | Wrong/inconsistent results | Unsynchronized access to shared state |
   | **Deadlock** | Complete hang, no progress | Circular wait for locks |
   | **Livelock** | CPU busy but no progress | Threads keep yielding to each other |
   | **Priority Inversion** | High-priority task blocked | Low-priority holds resource needed by high |

   **Initial Characterization:**

   Answer these questions:
   1. **Reproducibility**: How often? (1/10? 1/1000?)
   2. **Timing**: CPU-bound or I/O-bound? Fast or slow machines?
   3. **Scale**: Single-threaded works? Fails at N threads?
   4. **Symptom**: Hang? Crash? Wrong data? Performance?

   ```bash
   # Reproduce with stress
   for i in {1..100}; do ./test && echo "PASS $i" || echo "FAIL $i"; done | grep FAIL | wc -l
   ```

   **Identify All Shared State:**

   Find every instance of shared mutable data:
   ```bash
   # C++: Find globals, statics, class members accessed from multiple threads
   grep -rn "static\|global\|mutex\|atomic\|volatile" src/

   # Python: Find module-level variables, class variables
   grep -rn "^[a-zA-Z_].*=\|cls\.\|self\.__class__" src/

   # Look for shared resources
   grep -rn "singleton\|getInstance\|shared_ptr\|global" src/
   ```

   **Shared state checklist:**
   - [ ] Global variables
   - [ ] Static class members
   - [ ] Singleton instances
   - [ ] Caches
   - [ ] Connection pools
   - [ ] File handles
   - [ ] Database connections

   **Map the Concurrency Model:**

   Draw the thread/task interactions:
   ```
   Thread A          Thread B          Shared State
       |                 |                  |
       |--- read ------->|                  |
       |                 |--- write ------->|
       |--- write ------>|                  |  ← RACE!
   ```

   Questions to answer:
   - Which threads/tasks access which data?
   - What synchronization exists? (locks, atomics, channels)
   - What ordering is assumed vs guaranteed?

### Phase 2: Pattern Analysis

1. **Find Working Examples**
   - Locate similar working code in same codebase
   - What works that's similar to what's broken?

2. **Compare Against References**
   - If implementing pattern, read reference implementation COMPLETELY
   - Don't skim - read every line

3. **Identify Differences**
   - What's different between working and broken?
   - List every difference, however small

4. **Understand Dependencies**
   - What other components does this need?
   - What settings, config, environment?

### Phase 3: Hypothesis and Testing

1. **Form Single Hypothesis**
   - State clearly: "I think X is the root cause because Y"
   - Be specific, not vague

2. **Test Minimally**
   - Make the SMALLEST possible change to test hypothesis
   - One variable at a time
   - Don't fix multiple things at once

3. **Verify Before Continuing**
   - Did it work? Yes → Phase 4
   - Didn't work? Form NEW hypothesis
   - DON'T add more fixes on top

4. **When You Don't Know**
   - Say "I don't understand X"
   - Don't pretend to know

### Phase 4: Implementation

1. **Create Failing Test Case**
   - **REQUIRED:** Use the `test-driven-development` skill
   - MUST have before fixing

2. **Implement Single Fix**
   - Address the root cause identified
   - ONE change at a time
   - No "while I'm here" improvements

3. **Verify Fix**
   - Test passes now?
   - No other tests broken?

4. **If Fix Doesn't Work**
   - STOP
   - Count: How many fixes have you tried?
   - If < 3: Return to Phase 1, re-analyze
   - **If ≥ 3: STOP and question the architecture**

5. **If 3+ Fixes Failed: Question Architecture**

   **Pattern indicating architectural problem:**
   - Each fix reveals new shared state/coupling
   - Fixes require "massive refactoring"
   - Each fix creates new symptoms elsewhere

   **STOP and question fundamentals:**
   - Is this pattern fundamentally sound?
   - Should we refactor architecture vs. continue fixing symptoms?

## Red Flags - STOP and Follow Process

If you catch yourself thinking:
- "Quick fix for now, investigate later"
- "Just try changing X and see if it works"
- "It's probably X, let me fix that"
- "I don't fully understand but this might work"
- Proposing solutions before tracing data flow
- "One more fix attempt" (when already tried 2+)

**ALL of these mean: STOP. Return to Phase 1.**

## Common Rationalizations

| Excuse | Reality |
|--------|---------|
| "Issue is simple, don't need process" | Simple issues have root causes too |
| "Emergency, no time for process" | Systematic is FASTER than thrashing |
| "Just try this first, then investigate" | First fix sets the pattern. Do it right. |
| "I'll write test after confirming fix" | Untested fixes don't stick |
| "One more fix attempt" (after 2+) | 3+ failures = architectural problem |

## Quick Reference

| Phase | Key Activities | Success Criteria |
|-------|---------------|------------------|
| **1. Root Cause** | Read errors, reproduce, check changes | Understand WHAT and WHY |
| **2. Pattern** | Find working examples, compare | Identify differences |
| **3. Hypothesis** | Form theory, test minimally | Confirmed or new hypothesis |
| **4. Implementation** | Create test, fix, verify | Bug resolved, tests pass |

## Escalation Triggers

| Situation | Escalate To |
|-----------|-------------|
| Root cause spans multiple systems | Ask user, involve system owners |
| Fix requires changing public API | Ask user about backwards compatibility |
| Bug reveals security vulnerability | `security-reviewer` agent |
| 3+ fix attempts failed | Question architecture with user |
| Root cause in third-party library | Report finding, ask user for guidance |
| Race condition suspected in 3+ locations | `orchestrator` agent for planning |
| Need git history context | `git-expert` agent |
| Multi-service concurrency issue | `devops-troubleshooter` agent |
| Cannot reproduce locally | Ask user for exact reproduction steps |
| Test flakiness across suites | Isolate polluting test, apply defense-in-depth |

**How to escalate:**
```
BLOCKED: [brief description]
Root cause: [what you found]
Evidence: [key data points]
Attempted: [what you tried]
Recommendation: [suggested path forward]
```

## Concurrency-Specific Debugging Patterns

When Phase 1 identifies a concurrency issue, use these specialized techniques:

### Race Condition Analysis

**Pattern**: Read-modify-write without atomicity
```cpp
// BAD - race between read and write
if (counter < MAX) {     // Thread A reads
    counter++;           // Thread B also read, both increment
}

// GOOD - atomic operation
if (counter.fetch_add(1) < MAX) { ... }

// GOOD - mutex protection
std::lock_guard<std::mutex> lock(mutex);
if (counter < MAX) { counter++; }
```

**Detection tools:**
```bash
# ThreadSanitizer (C++/C)
clang++ -fsanitize=thread -g program.cpp
./a.out

# Helgrind (Valgrind)
valgrind --tool=helgrind ./program

# Go race detector
go test -race ./...
go run -race main.go
```

### Deadlock Analysis

**Classic pattern**: Lock ordering violation
```cpp
// Thread A: locks M1, then M2
// Thread B: locks M2, then M1
// → Deadlock when A holds M1 waiting for M2, B holds M2 waiting for M1
```

**Detection:**
```bash
# GDB - get stack traces of all threads
gdb -p <pid>
(gdb) thread apply all bt

# pstack (Linux)
pstack <pid>

# lldb (macOS)
lldb -p <pid>
(lldb) bt all
```

**Prevention:**
1. Always acquire locks in consistent global order
2. Use `std::scoped_lock` (C++17) for multiple locks
3. Use timeouts: `try_lock_for()`
4. Prefer lock-free data structures

### Fix Patterns for Concurrency

**Eliminate Sharing (Best Option):**
```cpp
// BAD - shared counter
static int globalCounter;

// GOOD - thread-local + merge
thread_local int localCounter;
// ... work ...
// merge at end under lock
```

**Proper Synchronization:**

Mutex (exclusive access):
```cpp
// C++
std::mutex mtx;
{
    std::lock_guard<std::mutex> lock(mtx);
    // critical section
}

// Python
import threading
lock = threading.Lock()
with lock:
    # critical section

// Go
var mu sync.Mutex
mu.Lock()
defer mu.Unlock()
// critical section
```

Read-Write Lock (many readers, one writer):
```cpp
std::shared_mutex rw;
{
    std::shared_lock<std::shared_mutex> read(rw);  // readers
    // read shared data
}
{
    std::unique_lock<std::shared_mutex> write(rw);  // writers
    // modify shared data
}
```

Atomics (lock-free for simple types):
```cpp
std::atomic<int> counter{0};
counter.fetch_add(1);  // thread-safe increment

std::atomic<bool> flag{false};
flag.store(true);
if (flag.load()) { ... }
```

Channels (message passing):
```go
// Go - prefer channels over shared memory
ch := make(chan Result)
go func() { ch <- computeResult() }()
result := <-ch
```

```python
# Python - Queue for thread communication
import queue
q = queue.Queue()
# Producer
q.put(item)
# Consumer
item = q.get()
```

### Language-Specific Tools

| Language | Race Detector | Deadlock Detector |
|----------|---------------|-------------------|
| C/C++ | ThreadSanitizer, Helgrind | GDB, Helgrind |
| Go | `go run -race` | `GODEBUG=schedtrace=1000` |
| Rust | Compile-time (ownership) | `parking_lot` deadlock detection |
| Python | N/A (GIL limits) | `faulthandler`, `py-spy` |
| Java | `-XX:+PrintConcurrentLocks` | jstack, VisualVM |

### Verification of Concurrency Fixes

After fixing concurrency bugs, ALWAYS:
1. Run with ThreadSanitizer/race detector (must pass clean)
2. Stress test: run 1000x under load
3. Test on slow/fast machines
4. Test with different thread counts

```bash
# Stress test
for threads in 1 2 4 8 16; do
    echo "Testing with $threads threads"
    THREADS=$threads ./test --repeat=100
done
```

### Common Concurrency Mistakes

| Mistake | Why It's Wrong | Fix |
|---------|----------------|-----|
| "Just add a lock" | May cause deadlock or perf issues | Understand access pattern first |
| Double-checked locking | Broken without proper barriers | Use `std::call_once` or atomic |
| Volatile = thread-safe | Volatile ≠ atomic | Use `std::atomic` |
| "It passed 100 times" | Races are probabilistic | Use sanitizers |
| Lock inside loop | Performance killer | Batch or restructure |

## Failure Behavior

- **Cannot reproduce:** Document steps tried, ask for exact reproduction steps
- **Root cause unclear after Phase 1:** Re-gather evidence, don't guess
- **Fix doesn't work:** Return to Phase 1, don't stack more fixes
- **3+ failures:** Stop fixing, recommend architectural review
- **Race condition passes local tests:** Use ThreadSanitizer or stress testing before declaring fixed

## Integration with Other Skills

**This skill requires using:**
- **test-driven-development** skill - REQUIRED for creating failing test case (Phase 4)

**Complementary skills:**
- **security-reviewer** agent - Multi-layer validation section for defense-in-depth
- **verification-before-completion** skill - Verify fix worked before claiming success

**Techniques included in this skill:**
- Root cause tracing for deep call stacks (Phase 1 step 5)
- Condition-based waiting to replace arbitrary timeouts (Phase 2)
- Concurrency debugging for race conditions and deadlocks (Phase 1 step 6)

## Save Learnings to Memory

After fixing non-trivial bugs, persist insights:
```
add_observations: [{
  entityName: "ProjectName",
  contents: [
    "Bug: [symptom] caused by [root cause]",
    "Fix: [solution] in [file:line]",
    "Pattern: [general lesson for future]"
  ]
}]
```

This prevents re-discovering the same issues across sessions.

## Real-World Impact

From debugging sessions:
- Systematic approach: 15-30 minutes to fix
- Random fixes approach: 2-3 hours of thrashing
- First-time fix rate: 95% vs 40%
- New bugs introduced: Near zero vs common

## Related Skills

- **test-driven-development**: Write tests to prevent regression
- **verification-before-completion**: Verify fix before claiming done

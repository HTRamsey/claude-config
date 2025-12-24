---
name: concurrency-debugging
description: "Use when debugging race conditions, deadlocks, thread safety issues, data races, or priority inversion. Triggers: flaky behavior, 'works sometimes', hangs, corrupted data under load."
---

# Concurrency Debugging

Systematic methodology for diagnosing and fixing concurrency bugs - the hardest class of bugs because they're non-deterministic and hard to reproduce.

## Persona

Concurrency specialist who has debugged distributed systems and real-time applications. Assumes all shared mutable state is suspicious until proven safe. Insists on understanding the bug before attempting fixes.

## When to Use

- Test passes locally but fails in CI (timing-dependent)
- Application hangs intermittently
- Data corruption under concurrent load
- "Works fine until we added threads"
- Performance degrades non-linearly with concurrency

## The Four Concurrency Bug Types

| Type | Symptom | Root Cause |
|------|---------|------------|
| **Race Condition** | Wrong/inconsistent results | Unsynchronized access to shared state |
| **Deadlock** | Complete hang, no progress | Circular wait for locks |
| **Livelock** | CPU busy but no progress | Threads keep yielding to each other |
| **Priority Inversion** | High-priority task blocked | Low-priority holds resource needed by high |

## Diagnosis Process

### Step 1: Characterize the Bug

Answer these questions:
1. **Reproducibility**: How often? (1/10? 1/1000?)
2. **Timing**: CPU-bound or I/O-bound? Fast or slow machines?
3. **Scale**: Single-threaded works? Fails at N threads?
4. **Symptom**: Hang? Crash? Wrong data? Performance?

```bash
# Reproduce with stress
for i in {1..100}; do ./test && echo "PASS $i" || echo "FAIL $i"; done | grep FAIL | wc -l
```

### Step 2: Identify Shared State

Find ALL shared mutable state:

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

### Step 3: Map the Concurrency Model

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

### Step 4: Apply Bug-Specific Analysis

#### Race Condition Analysis

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

**Detection techniques:**
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

#### Deadlock Analysis

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

#### Priority Inversion Analysis

**Pattern**: Low-priority thread holds lock needed by high-priority
```
High Priority: [blocked waiting for lock]
Med Priority:  [running, preempting Low]
Low Priority:  [holds lock, can't run to release it]
```

**Fix**: Priority inheritance (OS/RTOS feature) or avoid sharing between priority levels.

### Step 5: Instrument and Reproduce

Add logging to narrow down:

```cpp
// C++ - minimal overhead logging
#define TRACE(msg) fprintf(stderr, "[%lu] %s:%d %s\n", \
    pthread_self(), __FILE__, __LINE__, msg)

// Before critical sections
TRACE("acquiring lock X");
lock.lock();
TRACE("acquired lock X");
```

```python
# Python - thread-safe logging
import logging
import threading
logging.basicConfig(format='%(threadName)s: %(message)s')
logger = logging.getLogger()

logger.info("acquiring lock")
```

**Reproduce more reliably:**
```cpp
// Add artificial delays to widen race window
std::this_thread::sleep_for(std::chrono::milliseconds(1));

// Or use ThreadSanitizer which adds delays automatically
```

## Fix Patterns

### Eliminate Sharing
Best fix is no shared state:
```cpp
// BAD - shared counter
static int globalCounter;

// GOOD - thread-local + merge
thread_local int localCounter;
// ... work ...
// merge at end under lock
```

### Proper Synchronization

**Mutex (exclusive access):**
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

**Read-Write Lock (many readers, one writer):**
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

**Atomics (lock-free for simple types):**
```cpp
std::atomic<int> counter{0};
counter.fetch_add(1);  // thread-safe increment

std::atomic<bool> flag{false};
flag.store(true);
if (flag.load()) { ... }
```

**Channels (message passing):**
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

### Lock Ordering
```cpp
// Define global order: always lock A before B before C
void safeOperation() {
    std::scoped_lock lock(mutexA, mutexB, mutexC);  // deadlock-free
    // ...
}
```

## Language-Specific Tools

| Language | Race Detector | Deadlock Detector |
|----------|---------------|-------------------|
| C/C++ | ThreadSanitizer, Helgrind | GDB, Helgrind |
| Go | `go run -race` | `GODEBUG=schedtrace=1000` |
| Rust | Compile-time (ownership) | `parking_lot` deadlock detection |
| Python | N/A (GIL limits) | `faulthandler`, `py-spy` |
| Java | `-XX:+PrintConcurrentLocks` | jstack, VisualVM |

## Common Mistakes

| Mistake | Why It's Wrong | Fix |
|---------|----------------|-----|
| "Just add a lock" | May cause deadlock or perf issues | Understand access pattern first |
| Double-checked locking | Broken without proper barriers | Use `std::call_once` or atomic |
| Volatile = thread-safe | Volatile ≠ atomic | Use `std::atomic` |
| "It passed 100 times" | Races are probabilistic | Use sanitizers |
| Lock inside loop | Performance killer | Batch or restructure |

## Should NOT Attempt

- Fixing without understanding the race (will just move the bug)
- Adding sleep() as a "fix" (masks, doesn't fix)
- Removing synchronization to "improve performance"
- Assuming single-threaded testing proves correctness

## Escalation

- If bug is in library code → report upstream with minimal reproducer
- If architectural issue → `refactoring-planner` agent
- If Qt-specific threading → `qt-expert` agent
- If test flakiness → `flaky-test-fixer` agent
- If performance vs correctness tradeoff → discuss with user

## Verification

After fixing:
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

# Concurrency Debugging Reference

Specialized techniques for race conditions, deadlocks, and thread safety issues.

## The Four Concurrency Bug Types

| Type | Symptom | Root Cause |
|------|---------|------------|
| **Race Condition** | Wrong/inconsistent results | Unsynchronized access to shared state |
| **Deadlock** | Complete hang, no progress | Circular wait for locks |
| **Livelock** | CPU busy but no progress | Threads keep yielding to each other |
| **Priority Inversion** | High-priority task blocked | Low-priority holds resource needed by high |

## Initial Characterization

Answer these questions first:
1. **Reproducibility**: How often? (1/10? 1/1000?)
2. **Timing**: CPU-bound or I/O-bound? Fast or slow machines?
3. **Scale**: Single-threaded works? Fails at N threads?
4. **Symptom**: Hang? Crash? Wrong data? Performance?

```bash
# Reproduce with stress
for i in {1..100}; do ./test && echo "PASS $i" || echo "FAIL $i"; done | grep FAIL | wc -l
```

## Identify All Shared State

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

## Map the Concurrency Model

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

## Race Condition Analysis

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

## Deadlock Analysis

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

## Fix Patterns

### Eliminate Sharing (Best Option)
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

## Language-Specific Tools

| Language | Race Detector | Deadlock Detector |
|----------|---------------|-------------------|
| C/C++ | ThreadSanitizer, Helgrind | GDB, Helgrind |
| Go | `go run -race` | `GODEBUG=schedtrace=1000` |
| Rust | Compile-time (ownership) | `parking_lot` deadlock detection |
| Python | N/A (GIL limits) | `faulthandler`, `py-spy` |
| Java | `-XX:+PrintConcurrentLocks` | jstack, VisualVM |

## Verification of Fixes

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

## Common Mistakes

| Mistake | Why It's Wrong | Fix |
|---------|----------------|-----|
| "Just add a lock" | May cause deadlock or perf issues | Understand access pattern first |
| Double-checked locking | Broken without proper barriers | Use `std::call_once` or atomic |
| Volatile = thread-safe | Volatile ≠ atomic | Use `std::atomic` |
| "It passed 100 times" | Races are probabilistic | Use sanitizers |
| Lock inside loop | Performance killer | Batch or restructure |

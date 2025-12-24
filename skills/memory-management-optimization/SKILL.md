---
name: memory-management-optimization
description: "Use when debugging memory leaks, profiling memory usage, or optimizing allocations. Triggers: 'memory leak', 'out of memory', 'growing memory', 'heap profiling', 'allocation'."
---

# Memory Management Optimization

Systematic methodology for finding memory leaks, profiling memory usage, and optimizing allocation patterns. Covers C++ (Valgrind, ASAN, RAII), Python (tracemalloc, objgraph), and general optimization patterns.

## Persona

Memory systems expert who has optimized applications from embedded systems to servers. Believes that measuring is better than guessing, and that the best allocation is one you don't make.

## When to Use

- Memory usage grows over time (leak)
- Out-of-memory errors or crashes
- Performance issues from allocation overhead
- Need to reduce memory footprint
- Profiling before optimization

## Diagnosis Process

### Step 1: Measure Current State

**C++ with Valgrind:**
```bash
# Full leak check
valgrind --leak-check=full --show-leak-kinds=all ./program

# Track origins of uninitialized values
valgrind --track-origins=yes ./program

# Heap profiler
valgrind --tool=massif ./program
ms_print massif.out.*
```

**C++ with AddressSanitizer (faster):**
```bash
# Compile with ASAN
clang++ -fsanitize=address -g program.cpp -o program
./program

# Or with GCC
g++ -fsanitize=address -g program.cpp -o program
```

**Python:**
```python
import tracemalloc

tracemalloc.start()

# ... run code ...

snapshot = tracemalloc.take_snapshot()
top_stats = snapshot.statistics('lineno')

print("[ Top 10 memory allocations ]")
for stat in top_stats[:10]:
    print(stat)
```

**General (Linux):**
```bash
# Watch process memory over time
watch -n 1 'ps -o pid,vsz,rss,comm -p <PID>'

# Detailed memory map
pmap -x <PID>

# System-wide
free -h
cat /proc/meminfo
```

### Step 2: Identify Leak Type

| Type | Symptom | Cause |
|------|---------|-------|
| **Definite leak** | Memory never freed | Missing delete/free |
| **Possible leak** | Pointer still reachable but likely lost | Complex ownership |
| **Still reachable** | Memory reachable at exit | Intentional (singletons) |
| **Logical leak** | Growing containers | Never removing items |

### Step 3: Find the Source

**Valgrind output interpretation:**
```
==12345== 1,024 bytes in 1 blocks are definitely lost
==12345==    at 0x4C2FB0F: malloc (vg_replace_malloc.c:299)
==12345==    by 0x401234: MyClass::allocate() (myclass.cpp:42)
==12345==    by 0x401567: main (main.cpp:15)
```
→ Leak at `myclass.cpp:42`, called from `main.cpp:15`

**ASAN output:**
```
==12345==ERROR: LeakSanitizer: detected memory leaks

Direct leak of 1024 byte(s) in 1 object(s) allocated from:
    #0 0x7f... in malloc
    #1 0x401234 in MyClass::allocate() myclass.cpp:42
    #2 0x401567 in main main.cpp:15
```

## Fix Patterns

### C++: RAII (Resource Acquisition Is Initialization)
```cpp
// BAD - manual memory management
void process() {
    char* buffer = new char[1024];
    doSomething(buffer);  // If this throws, leak!
    delete[] buffer;
}

// GOOD - RAII with smart pointers
void process() {
    auto buffer = std::make_unique<char[]>(1024);
    doSomething(buffer.get());  // Auto-freed even on exception
}

// GOOD - use containers
void process() {
    std::vector<char> buffer(1024);
    doSomething(buffer.data());
}
```

### Smart Pointer Selection
```cpp
// Unique ownership (default choice)
std::unique_ptr<Widget> widget = std::make_unique<Widget>();

// Shared ownership (reference counted)
std::shared_ptr<Widget> shared = std::make_shared<Widget>();

// Non-owning reference to shared
std::weak_ptr<Widget> weak = shared;

// Qt parent-child (Qt takes ownership)
QWidget* child = new QWidget(parent);  // parent deletes child
```

### Container Memory Management
```cpp
// Clear doesn't free capacity
std::vector<int> v(1000000);
v.clear();  // size=0, capacity still 1000000!

// Actually free memory
v.clear();
v.shrink_to_fit();

// Or swap with empty
std::vector<int>().swap(v);

// Reserve to avoid reallocations
std::vector<int> v;
v.reserve(expectedSize);  // One allocation
for (int i = 0; i < expectedSize; i++) {
    v.push_back(i);  // No reallocation
}
```

### Python Memory Management
```python
# Find reference cycles
import gc
gc.collect()  # Force collection
print(gc.garbage)  # Uncollectable objects

# Break reference cycles
import weakref
class Node:
    def __init__(self):
        self.parent = None  # Strong ref - can cause cycle

class NodeFixed:
    def __init__(self):
        self._parent = None

    @property
    def parent(self):
        return self._parent() if self._parent else None

    @parent.setter
    def parent(self, p):
        self._parent = weakref.ref(p) if p else None
```

### Memory Pools (High-Performance)
```cpp
// Pre-allocate pool for fixed-size objects
template<typename T, size_t PoolSize>
class ObjectPool {
    std::array<std::aligned_storage_t<sizeof(T), alignof(T)>, PoolSize> pool;
    std::bitset<PoolSize> used;

public:
    T* allocate() {
        for (size_t i = 0; i < PoolSize; i++) {
            if (!used[i]) {
                used[i] = true;
                return reinterpret_cast<T*>(&pool[i]);
            }
        }
        return nullptr;  // Pool exhausted
    }

    void deallocate(T* ptr) {
        size_t index = reinterpret_cast<std::aligned_storage_t<sizeof(T), alignof(T)>*>(ptr) - pool.data();
        used[index] = false;
    }
};
```

### Arena Allocator (Bulk Free)
```cpp
// Allocate many, free all at once
class Arena {
    std::vector<char> buffer;
    size_t offset = 0;

public:
    Arena(size_t size) : buffer(size) {}

    void* allocate(size_t size, size_t align = alignof(std::max_align_t)) {
        size_t aligned = (offset + align - 1) & ~(align - 1);
        if (aligned + size > buffer.size()) return nullptr;
        void* ptr = buffer.data() + aligned;
        offset = aligned + size;
        return ptr;
    }

    void reset() { offset = 0; }  // "Free" everything
};
```

## Optimization Patterns

### Reduce Allocations
```cpp
// BAD - allocation per iteration
for (int i = 0; i < 1000; i++) {
    std::string s = buildString(i);  // Allocates each time
    process(s);
}

// GOOD - reuse buffer
std::string s;
for (int i = 0; i < 1000; i++) {
    s.clear();  // Keeps capacity
    buildStringInto(s, i);
    process(s);
}
```

### Small String Optimization (SSO)
```cpp
// std::string typically stores small strings inline (no allocation)
std::string small = "hello";  // Usually no heap allocation (<= 15-22 chars)
std::string large = "this is a much longer string...";  // Heap allocated
```

### Move Semantics
```cpp
// BAD - copies large object
std::vector<int> createVector() {
    std::vector<int> v(1000000);
    return v;  // Copy? No, actually moved (RVO/NRVO)
}

// Explicit move when needed
std::vector<int> v1(1000000);
std::vector<int> v2 = std::move(v1);  // v1 now empty, no copy
```

## Common Leaks

| Pattern | Example | Fix |
|---------|---------|-----|
| Missing delete | `new X` without `delete` | Use `unique_ptr` |
| Exception path | `delete` after throwing code | RAII |
| Circular refs | A→B→A | `weak_ptr`, break cycle |
| Growing cache | Cache without eviction | Add size limit, LRU |
| Event handlers | Qt connections to deleted objects | Disconnect or parent ownership |
| Global containers | Static `vector` that grows | Clear on shutdown or limit |

## Should NOT Attempt

- Optimizing without profiling first
- Premature optimization of non-hot paths
- Removing smart pointers for "performance"
- Manual memory management when RAII works
- Ignoring "still reachable" as always benign

## Escalation

- Threading issues with memory → `concurrency-debugging` skill
- Qt-specific ownership → `qt-expert` agent
- System-level memory issues → `devops-troubleshooter`
- Need architectural changes → `refactoring-planner`

## Verification

After fixing:
1. Run Valgrind/ASAN - should show zero leaks
2. Monitor memory over time - should stabilize
3. Stress test - memory should not grow unbounded
4. Measure performance - ensure no regression

```bash
# Verify no leaks
valgrind --leak-check=full --error-exitcode=1 ./program

# Memory over time
while true; do ps -o rss= -p <PID>; sleep 1; done | head -100
```

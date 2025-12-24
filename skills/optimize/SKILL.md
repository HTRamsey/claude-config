---
name: optimize
description: Use for performance optimization when code is slow, memory-hungry, or has bottlenecks. Triggers on "slow", "performance", "optimize", profiling requests. Requires measurement before and after every change.
---

# Performance Optimization

**Persona:** Data-driven optimizer who measures before and after every change.

## Should NOT Attempt

- Optimize without profiling first (no guessing)
- Make multiple optimizations before measuring each
- Sacrifice correctness for performance
- Optimize code that isn't in the hot path
- Skip regression testing after optimization

## Workflow

1. **Measure First** - Profile, don't guess. Establish baseline.
2. **Analyze Hotspots** - CPU, memory, I/O, concurrency
3. **Optimize** - Apply fixes
4. **Verify** - Re-measure, ensure correctness
5. **Document** - Record what was slow and improvement metrics

## Profiling Tools

| Language | CPU | Memory | Command |
|----------|-----|--------|---------|
| Python | py-spy | memray | `py-spy record -o profile.svg -- python script.py` |
| Node.js | clinic.js | heapdump | `clinic flame -- node app.js` |
| Rust | flamegraph | heaptrack | `cargo flamegraph` |
| Go | pprof | pprof | `go tool pprof cpu.prof` |
| C/C++ | perf | valgrind | `perf record ./binary && perf report` |

**Benchmarking:** `hyperfine 'old_cmd' 'new_cmd' --export-markdown comparison.md`

## Common Optimizations

| Area | Fixes |
|------|-------|
| Algorithmic | O(n^2)->O(n log n), cache results, early exit |
| Memory | Avoid copies, reserve capacity, pool allocations |
| I/O | Batch ops, async/parallel, buffer, connection pool |
| Concurrency | Reduce lock scope, lock-free structures, batch work |

## Flamegraph Reading

- **Width** = Time spent (optimize wide bars)
- **Height** = Call stack depth
- **Plateaus** = Blocking (consider async)
- Focus on widest bars at bottom

## Quick Wins Checklist

- [ ] N+1 queries? (add eager loading)
- [ ] Missing database indexes?
- [ ] Unnecessary logging in hot path?
- [ ] Synchronous I/O that could be async?
- [ ] Recomputing same values? (add memoization)
- [ ] Large allocations in loops? (reuse buffers)

## Examples

### Example 1: Slow API Endpoint
**Symptom:** `/api/users` takes 3 seconds
**Profile:** `py-spy record -o profile.svg -- python app.py`
**Finding:** N+1 queries - 100 separate DB calls
**Fix:** Add eager loading: `User.query.options(joinedload(User.posts))`
**Result:** 3s → 150ms (20x improvement)

### Example 2: Memory Spike
**Symptom:** Process OOMs processing large CSV
**Profile:** `memray run script.py && memray flamegraph`
**Finding:** Loading entire file into memory
**Fix:** Stream with generator: `for row in csv.reader(f)`
**Result:** 2GB peak → 50MB constant

### Example 3: Slow Build
**Symptom:** TypeScript build takes 45 seconds
**Profile:** `tsc --generateTrace trace && analyze-trace trace`
**Finding:** Excessive type inference in generic function
**Fix:** Add explicit type annotations
**Result:** 45s → 12s (4x improvement)

## Escalation Triggers

| Situation | Escalate To |
|-----------|-------------|
| Algorithmic complexity issue (O(n²+)) | Plan redesign, ask user |
| Database query optimization needed | `database-optimizer` agent |
| Memory leak suspected | Dedicated profiling session |
| Concurrency bottleneck | Architecture review |
| Optimization requires breaking API | Ask user for approval |

## Failure Behavior

- **No improvement found:** Report findings, suggest architectural changes
- **Regression introduced:** Roll back, document failed approach
- **Cannot profile:** Report tooling issue, suggest alternatives
- **Optimization breaks tests:** Reject change, fix first

## Related

- `perf-reviewer` agent - Automated detection
- `observability-logging` - Measure with instrumentation

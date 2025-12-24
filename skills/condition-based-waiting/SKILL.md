---
name: condition-based-waiting
description: Use when tests have race conditions, timing dependencies, or inconsistent pass/fail behavior - replaces arbitrary timeouts with condition polling to wait for actual state changes, eliminating flaky tests from timing guesses
---

# Condition-Based Waiting

**Persona:** Reliability engineer who eliminates flakiness through deterministic waits.

**Core principle:** Wait for the actual condition you care about, not a guess about how long it takes.

## Should NOT Attempt

- Replace timeouts that are testing actual timing behavior (debounce, throttle)
- Poll too frequently (<10ms intervals)
- Wait without timeout (infinite loop risk)
- Use for synchronous code (condition-based waiting is for async)

## When to Use

| Use When | Don't Use When |
|----------|----------------|
| Tests have arbitrary delays | Testing actual timing (debounce, throttle) |
| Tests are flaky under load | Document WHY if using arbitrary timeout |
| Waiting for async operations | |

## Core Pattern

```typescript
// BEFORE: Guessing at timing
await new Promise(r => setTimeout(r, 50));
expect(getResult()).toBeDefined();

// AFTER: Waiting for condition
await waitFor(() => getResult() !== undefined);
expect(getResult()).toBeDefined();
```

## Quick Patterns

| Scenario | Pattern |
|----------|---------|
| Wait for event | `waitFor(() => events.find(e => e.type === 'DONE'))` |
| Wait for state | `waitFor(() => machine.state === 'ready')` |
| Wait for count | `waitFor(() => items.length >= 5)` |
| Wait for file | `waitFor(() => fs.existsSync(path))` |

## Implementation

```typescript
async function waitFor<T>(
  condition: () => T | undefined | null | false,
  description: string,
  timeoutMs = 5000
): Promise<T> {
  const startTime = Date.now();
  while (true) {
    const result = condition();
    if (result) return result;
    if (Date.now() - startTime > timeoutMs) {
      throw new Error(`Timeout waiting for ${description} after ${timeoutMs}ms`);
    }
    await new Promise(r => setTimeout(r, 10)); // Poll every 10ms
  }
}
```

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Polling too fast (1ms) | Poll every 10ms |
| No timeout | Always include timeout with clear error |
| Stale data (cache before loop) | Call getter inside loop |

## When Arbitrary Timeout IS Correct

```typescript
await waitForEvent(manager, 'TOOL_STARTED'); // First: wait for condition
await new Promise(r => setTimeout(r, 200));   // Then: known timing (2 ticks at 100ms)
// ^^^ Document WHY with comment
```

## Output Format

When fixing flaky tests:
```
FLAKY TEST FIX: [test name]

Root cause: [arbitrary timeout | race condition | shared state]

Before:
```[original code with timeout]```

After:
```[fixed code with condition-based wait]```

Condition waited for: [what state change]
Impact: [expected reliability improvement]
```

## Escalation Triggers

| Situation | Escalate To |
|-----------|-------------|
| Condition never becomes true | `root-cause-tracing` skill |
| Race condition in production code | `systematic-debugging` skill |
| Flakiness persists after fix | Investigate shared state or test isolation |
| Performance test timing | Different approach needed (benchmarking) |

## Failure Behavior

- **Timeout reached:** Report what condition was expected, last observed state
- **Condition flapping:** Report instability, suggest investigating why state changes
- **Cannot identify condition:** Ask user what state change indicates completion
- **Polling overhead too high:** Suggest event-based waiting if available

## Impact

From debugging session: Fixed 15 flaky tests, 60%->100% pass rate, 40% faster execution.

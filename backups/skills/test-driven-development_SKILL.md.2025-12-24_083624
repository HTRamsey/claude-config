---
name: test-driven-development
description: Use when implementing any feature or bugfix, adding tests, or fixing flaky tests - covers TDD workflow (red-green-refactor), condition-based waiting for async tests, and testing anti-patterns to avoid (mock testing, test pollution, incomplete mocks)
---

# Test-Driven Development (TDD)

**Persona:** Disciplined craftsperson who refuses to write code without proof it's needed - if no test demands the code, the code doesn't exist yet.

## Overview

Write the test first. Watch it fail. Write minimal code to pass.

**Core principle:** If you didn't watch the test fail, you don't know if it tests the right thing.

**Violating the letter of the rules is violating the spirit of the rules.**

## When to Use

**Always:**
- New features
- Bug fixes
- Refactoring
- Behavior changes

**Exceptions (ask partner):**
- Throwaway prototypes
- Generated code
- Configuration files

Thinking "skip TDD just this once"? Stop. That's rationalization.

## The Iron Law

```
NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST
```

Write code before the test? Delete it. Start over.

**No exceptions:**
- Don't keep it as "reference"
- Don't "adapt" it while writing tests
- Don't look at it
- Delete means delete

Implement fresh from tests. Period.

## Should NOT Attempt

- Write implementation before test
- Keep "exploratory" code while writing tests
- Write tests that pass immediately
- Mock dependencies you don't understand
- Write multiple tests before implementing any
- Refactor during RED phase
- Add features during GREEN phase
- Skip the "watch it fail" step

## Red-Green-Refactor

### RED - Write Failing Test

Write one minimal test showing what should happen.

```typescript
// Good: Clear name, tests real behavior, one thing
test('retries failed operations 3 times', async () => {
  let attempts = 0;
  const operation = () => {
    attempts++;
    if (attempts < 3) throw new Error('fail');
    return 'success';
  };

  const result = await retryOperation(operation);

  expect(result).toBe('success');
  expect(attempts).toBe(3);
});
```

**Requirements:**
- One behavior
- Clear name
- Real code (no mocks unless unavoidable)

### Verify RED - Watch It Fail

**MANDATORY. Never skip.**

```bash
npm test path/to/test.test.ts
```

Confirm:
- Test fails (not errors)
- Failure message is expected
- Fails because feature missing (not typos)

**Test passes?** You're testing existing behavior. Fix test.

### GREEN - Minimal Code

Write simplest code to pass the test.

```typescript
// Good: Just enough to pass
async function retryOperation<T>(fn: () => Promise<T>): Promise<T> {
  for (let i = 0; i < 3; i++) {
    try {
      return await fn();
    } catch (e) {
      if (i === 2) throw e;
    }
  }
  throw new Error('unreachable');
}
```

Don't add features, refactor other code, or "improve" beyond the test.

### Verify GREEN - Watch It Pass

**MANDATORY.**

```bash
npm test path/to/test.test.ts
```

Confirm:
- Test passes
- Other tests still pass
- Output pristine (no errors, warnings)

### REFACTOR - Clean Up

After green only:
- Remove duplication
- Improve names
- Extract helpers

Keep tests green. Don't add behavior.

### Repeat

Next failing test for next feature.

## Good Tests

| Quality | Good | Bad |
|---------|------|-----|
| **Minimal** | One thing. "and" in name? Split it. | `test('validates email and domain and whitespace')` |
| **Clear** | Name describes behavior | `test('test1')` |
| **Shows intent** | Demonstrates desired API | Obscures what code should do |

## Why Order Matters

**"I'll write tests after to verify it works"**

Tests written after code pass immediately. Passing immediately proves nothing:
- Might test wrong thing
- Might test implementation, not behavior
- Might miss edge cases you forgot
- You never saw it catch the bug

Test-first forces you to see the test fail, proving it actually tests something.

## Common Rationalizations

| Excuse | Reality |
|--------|---------|
| "Too simple to test" | Simple code breaks. Test takes 30 seconds. |
| "I'll test after" | Tests passing immediately prove nothing. |
| "Already manually tested" | Ad-hoc ≠ systematic. No record, can't re-run. |
| "Deleting X hours is wasteful" | Sunk cost fallacy. Keeping unverified code is debt. |
| "TDD will slow me down" | TDD faster than debugging. Pragmatic = test-first. |

## Red Flags - STOP and Start Over

- Code before test
- Test after implementation
- Test passes immediately
- Can't explain why test failed
- Rationalizing "just this once"

**All of these mean: Delete code. Start over with TDD.**

## Escalation Triggers

**Escalate to human when:**
- Test framework not set up in project
- Unclear what behavior to test (requirements ambiguous)
- Testing requires mocking complex infrastructure you don't understand
- Test would require exposing internals that shouldn't be public
- Conflicting tests suggest design problem

**How to escalate:**
```
PAUSED TDD: [brief reason]
What I need: [specific clarification]
Options I see: [A, B, C]
Recommendation: [which and why]
```

## Verification Checklist

Before marking work complete:

- [ ] Every new function/method has a test
- [ ] Watched each test fail before implementing
- [ ] Each test failed for expected reason (feature missing, not typo)
- [ ] Wrote minimal code to pass each test
- [ ] All tests pass
- [ ] Output pristine (no errors, warnings)
- [ ] Tests use real code (mocks only if unavoidable)
- [ ] Edge cases and errors covered

Can't check all boxes? You skipped TDD. Start over.

## Debugging Integration

Bug found? Write failing test reproducing it. Follow TDD cycle. Test proves fix and prevents regression.

Never fix bugs without a test.

## Final Rule

```
Production code → test exists and failed first
Otherwise → not TDD
```

No exceptions without partner's permission.

## Advanced: Mutation Testing

After GREEN, verify test strength by introducing mutations:

### What is Mutation Testing?

1. **Generate mutants** - Automated tools make small code changes that should fail tests
2. **Run tests** - Do they catch (kill) the mutants?
3. **Surviving mutants** - Tests pass with bugs = weak tests!

### Common Mutations

| Original | Mutant | Should Fail |
|----------|--------|-------------|
| `a > b` | `a >= b` | Boundary test |
| `a && b` | `a \|\| b` | Logic test |
| `return x` | `return null` | Return value test |
| `x + 1` | `x - 1` | Arithmetic test |

### Tools by Language

```bash
# Python
pip install mutmut
mutmut run --paths-to-mutate=src/

# JavaScript/TypeScript
npm install --save-dev @stryker-mutator/core
npx stryker run

# Rust
cargo install cargo-mutants
cargo mutants

# Go
go install github.com/zimmski/go-mutesting/...
go-mutesting ./...
```

### When to Use

- Critical business logic
- Security-sensitive code
- After achieving high line coverage
- When you suspect tests are superficial

## Advanced: Property-Based Testing

Test invariants with generated inputs, not just examples.

### What is Property-Based Testing?

Instead of `test("1 + 1 = 2")`, test `for all x, y: x + y = y + x`

### Examples

```python
# Python with Hypothesis
from hypothesis import given, strategies as st

@given(st.lists(st.integers()))
def test_sort_preserves_length(xs):
    assert len(sorted(xs)) == len(xs)

@given(st.lists(st.integers()))
def test_sort_idempotent(xs):
    assert sorted(sorted(xs)) == sorted(xs)

@given(st.text())
def test_json_roundtrip(s):
    assert json.loads(json.dumps(s)) == s
```

```typescript
// TypeScript with fast-check
import fc from 'fast-check';

test('sort preserves elements', () => {
  fc.assert(fc.property(fc.array(fc.integer()), (arr) => {
    const sorted = [...arr].sort((a, b) => a - b);
    return arr.length === sorted.length &&
           arr.every(x => sorted.includes(x));
  }));
});
```

### Good Properties to Test

- **Roundtrip**: `decode(encode(x)) == x`
- **Idempotence**: `f(f(x)) == f(x)`
- **Commutativity**: `f(a, b) == f(b, a)`
- **Invariants**: `sort(x).length == x.length`
- **Oracle**: `fast_impl(x) == slow_but_correct_impl(x)`

### When to Use

- Serialization/parsing code
- Data transformations
- Mathematical operations
- State machines
- Any code with invariants

## Failure Behavior

**When test cannot be written first:**
1. Document why TDD isn't possible (no test framework, unclear requirements)
2. Mark code as UNTESTED with inline comment
3. Create follow-up task to add tests when blocker resolved
4. Never silently skip TDD

**When test passes immediately (didn't see red):**
1. STOP - this proves nothing
2. Either: test is wrong, or testing existing behavior
3. If testing existing: acknowledge and document
4. If test is wrong: delete and rewrite

## Async Testing: Condition-Based Waiting

Flaky tests often fail due to arbitrary timeouts. Replace guesses about timing with condition polling.

### The Problem

```typescript
// BEFORE: Guessing at timing
await new Promise(r => setTimeout(r, 50));
expect(getResult()).toBeDefined();
```

Arbitrary delays are unreliable:
- Fail under load
- Fail on slow systems
- Waste time with overestimated delays
- Race conditions still pass sometimes

### The Solution

```typescript
// AFTER: Waiting for the actual condition
await waitFor(() => getResult() !== undefined);
expect(getResult()).toBeDefined();
```

### Common Patterns

| Scenario | Pattern |
|----------|---------|
| Wait for event | `waitFor(() => events.find(e => e.type === 'DONE'))` |
| Wait for state | `waitFor(() => machine.state === 'ready')` |
| Wait for count | `waitFor(() => items.length >= 5)` |
| Wait for file | `waitFor(() => fs.existsSync(path))` |

### Implementation

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

### When Arbitrary Timeout IS Correct

```typescript
await waitForEvent(manager, 'TOOL_STARTED'); // First: wait for condition
await new Promise(r => setTimeout(r, 200));   // Then: known timing (2 ticks at 100ms)
// ^^^ Document WHY with comment - e.g., "Allow debounce period"
```

### Common Mistakes

| Mistake | Fix |
|---------|-----|
| Polling too fast (1ms) | Poll every 10ms - CPU waste |
| No timeout | Always include timeout with clear error message |
| Stale data (cache before loop) | Call getter inside condition loop each iteration |

### When NOT to Use

- Testing actual timing behavior (debounce, throttle) - use real timing
- Synchronous code - condition-based waiting is for async
- If condition never becomes true, escalate to `systematic-debugging` skill (Phase 1)

## Anti-Patterns: What NOT to Do

**Core principle:** Test what the code does, not what the mocks do.

### The Iron Laws

```
1. NEVER test mock behavior
2. NEVER add test-only methods to production classes
3. NEVER mock without understanding dependencies
```

### Anti-Pattern 1: Testing Mock Behavior

```typescript
// BAD: Testing that the mock exists
test('renders sidebar', () => {
  render(<Page />);
  expect(screen.getByTestId('sidebar-mock')).toBeInTheDocument();
});

// GOOD: Test real component or don't mock it
test('renders sidebar', () => {
  render(<Page />);  // Don't mock sidebar
  expect(screen.getByRole('navigation')).toBeInTheDocument();
});
```

**Gate function:** Before asserting on any mock element, ask: "Am I testing real behavior or just mock existence?" If testing mock existence → Delete assertion or unmock.

### Anti-Pattern 2: Test-Only Methods in Production

```typescript
// BAD: destroy() only used in tests
class Session {
  async destroy() {  // Looks like production API!
    await this._workspaceManager?.destroyWorkspace(this.id);
  }
}
afterEach(() => session.destroy());

// GOOD: Test utilities handle cleanup
// test-utils/session.ts
export async function cleanupSession(session: Session) {
  const workspace = session.getWorkspaceInfo();
  if (workspace) {
    await workspaceManager.destroyWorkspace(workspace.id);
  }
}
afterEach(() => cleanupSession(session));
```

**Why this matters:** Production class pollution is dangerous. Methods only for tests shouldn't exist in production.

### Anti-Pattern 3: Mocking Without Understanding

```typescript
// BAD: Mock breaks test logic
test('detects duplicate server', () => {
  // Mock prevents config write that test depends on!
  vi.mock('ToolCatalog', () => ({
    discoverAndCacheTools: vi.fn().mockResolvedValue(undefined)
  }));
  await addServer(config);
  await addServer(config);  // Should throw - but won't!
});

// GOOD: Understand dependencies first
test('detects duplicate server', () => {
  // Mock only the slow part, preserve behavior test needs
  vi.mock('MCPServerManager');

  await addServer(config);  // Config written
  await addServer(config);  // Duplicate detected
});
```

**Gate function before mocking:**
1. What side effects does the real method have?
2. Does this test depend on any of those side effects?
3. If yes → Mock at lower level, not the high-level method
4. If unsure → Run with real implementation FIRST, then add minimal mocking

### Anti-Pattern 4: Incomplete Mocks

```typescript
// BAD: Partial mock - only fields you think you need
const mockResponse = {
  status: 'success',
  data: { userId: '123', name: 'Alice' }
  // Missing: metadata that downstream code uses
};

// GOOD: Mirror real API completeness
const mockResponse = {
  status: 'success',
  data: { userId: '123', name: 'Alice' },
  metadata: { requestId: 'req-789', timestamp: 1234567890 }
};
```

### Red Flags - Stop and Fix

- Assertion checks for `*-mock` test IDs
- Methods only called in test files
- Mock setup is >50% of test
- Test fails when you remove mock
- Can't explain why mock is needed
- Mocking "just to be safe"

**Bottom line:** Mocks are tools to isolate, not things to test. If TDD reveals you're testing mock behavior, you've gone wrong.

## Related Skills

- **verification-before-completion** - Verify tests actually pass before claiming done
- **systematic-debugging** - When tests reveal unexpected failures

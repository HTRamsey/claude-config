# TDD Instructions (Tier 2)

**Iron Law:** No production code without a failing test first.

## Cycle

1. **RED** - Write ONE failing test
   - Clear name describing behavior
   - Run it, watch it fail
   - Confirm failure is for expected reason

2. **GREEN** - Write minimal code to pass
   - Just enough to make test green
   - No extra features

3. **REFACTOR** - Clean up
   - Only after tests pass
   - Keep tests green

## Mandatory Checks

Before each phase change:
- RED → GREEN: Saw test fail
- GREEN → REFACTOR: All tests pass
- REFACTOR → RED: Tests still pass

## Should NOT Do

- Write code before test
- Skip watching test fail
- Write multiple tests before implementing
- Refactor during RED phase
- Add features during GREEN phase

## Escalate When

- No test framework set up
- Requirements unclear
- Complex infrastructure mocking needed
- Tests suggest design problem

## Quick Commands

```bash
# Run specific test
npm test path/to/test.ts
pytest path/to/test.py
cargo test test_name

# Watch mode
npm test -- --watch
pytest --watch
```

For advanced topics (mutation testing, property-based testing, async patterns), see SKILL.md.

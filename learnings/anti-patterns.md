# Anti-Patterns

Things that seemed like good ideas but aren't.

## [2025-12-25] "When to Use" Section in Skill Body

**Problem:** Putting trigger conditions in the SKILL.md body instead of description
**Why it fails:** Body only loads AFTER skill triggers. Claude never sees body "When to Use" when deciding whether to activate.
**Fix:** All trigger conditions go in `description` field in frontmatter.

## [2025-12-25] Testing Mock Behavior

**Problem:** Writing tests that assert on mock elements (`*-mock` test IDs)
**Why it fails:** Tests pass because mock exists, not because feature works. Proves nothing about real behavior.
**Fix:** Test real components or don't mock. Ask: "Am I testing behavior or mock existence?"

## [2025-12-25] Test-Only Methods in Production Classes

**Problem:** Adding methods like `destroy()` or `reset()` to production classes only for test cleanup
**Why it fails:** Pollutes production API, methods look like real functionality, maintenance burden
**Fix:** Put test utilities in test-utils/ files, not in production classes.

## [2025-12-25] Mocking Without Understanding Dependencies

**Problem:** Mocking high-level methods without understanding their side effects
**Why it fails:** Test may depend on side effects the mock eliminates. Test passes but doesn't test real behavior.
**Fix:** Understand what real method does. Mock at lowest level needed. Run with real implementation first.

## [2025-12-25] Arbitrary Timeouts in Async Tests

**Problem:** Using `await sleep(50)` hoping it's long enough
**Why it fails:** Fails under load, fails on slow systems, wastes time with overestimates, flaky
**Fix:** Use condition-based waiting: `waitFor(() => result !== undefined)`. Only use timeouts for known timing requirements.

## [2025-12-25] Over-Explaining to Claude

**Problem:** Writing verbose skill instructions explaining concepts Claude already knows
**Why it fails:** Wastes tokens, clutters context, doesn't improve behavior
**Fix:** Claude is already smart. Only add context Claude doesn't have. Prefer examples over explanations.

## [2025-12-25] Proposing Fixes Before Root Cause

**Problem:** Seeing an error and immediately suggesting a fix
**Why it fails:** May fix symptom not cause. Creates new bugs. Wastes time on wrong approach.
**Fix:** Complete Phase 1 of systematic-debugging before any fix proposal. Understand before changing.

## [2025-12-25] YAML Values with Unquoted Colons

**Problem:** Writing `compatibility: C++: Valgrind` in frontmatter
**Why it fails:** YAML parser treats colon as nested mapping, breaks parsing
**Fix:** Quote values containing colons: `compatibility: "C++ requires Valgrind"`

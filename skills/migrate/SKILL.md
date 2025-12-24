---
name: migrate
description: Use when upgrading dependencies, migrating APIs, or updating deprecated code. Triggers on version upgrades, breaking changes, deprecation warnings. Ensures CI-safe incremental migration with rollback plans.
---

# Migration Skill

**Persona:** Methodical upgrader who never breaks the build.

## Should NOT Attempt

- Migrate all files in one commit
- Skip reading migration guides for major versions
- Proceed without green CI baseline
- Update deprecated APIs without understanding replacements
- Mix migration changes with feature work

## Workflow

| Phase | Actions |
|-------|---------|
| 1. Assess | List affected files, breaking changes, deprecations, review changelogs |
| 2. Plan | Order by dependencies (bottom-up), identify risks, plan rollback |
| 3. Prepare | Ensure tests pass, create branch, set up CI for target version |
| 4. Execute | Update imports -> fix API changes -> update deprecated calls -> test -> commit |
| 5. Verify | All tests pass, manual testing, performance check, no new warnings |

## Common Patterns

**API Renames:**
```bash
rg "oldFunction" --files-with-matches | xargs sed -i 's/oldFunction/newFunction/g'
```

**Type Changes:** Update signatures -> fix call sites -> check implicit conversions

**Removed Features:** Find usage (`rg "removedFeature"`) -> implement alternative -> update tests

## Examples

### Example 1: React 17 → 18
**Assess:** `rg "ReactDOM.render"` → 3 files affected
**Plan:** Update react-dom, then fix render calls
**Execute:**
1. `npm install react@18 react-dom@18`
2. Replace `ReactDOM.render(<App />, el)` with `createRoot(el).render(<App />)`
3. Run tests after each file
**Verify:** All tests pass, no console warnings

### Example 2: Python 3.9 → 3.11
**Assess:** Review changelog for breaking changes
**Plan:** Update CI first, then fix deprecated calls
**Execute:**
1. Update `.python-version` and CI config
2. `rg "typing.Dict|typing.List"` → replace with `dict`, `list`
3. Fix `asyncio.get_event_loop()` deprecation
**Verify:** `python -W error::DeprecationWarning -m pytest`

### Example 3: Express 4 → 5
**Assess:** Read migration guide, `rg "app\.(param|del)"` → 0 hits (no breaking patterns)
**Plan:** Simple version bump, watch for middleware changes
**Execute:** `npm install express@5`, run tests
**Verify:** Integration tests pass, monitor logs for warnings

## Escalation Triggers

| Situation | Escalate To |
|-----------|-------------|
| Breaking change affects core architecture | Ask user, consider phased approach |
| Deprecated feature has no replacement | Research alternatives, ask user |
| Migration introduces type errors in >10 files | Create branch, tackle incrementally |
| Performance regression detected | `perf-reviewer` agent |

## Failure Behavior

- **Tests fail mid-migration:** Commit working changes, report which file broke
- **Incompatible API change:** Research workarounds, report options
- **Build fails:** Roll back to last working commit, report specific error
- **Too many changes needed:** Break into smaller migrations, ask user to prioritize

## Notes

- Use TodoWrite to track migration steps
- One component at a time, test after each

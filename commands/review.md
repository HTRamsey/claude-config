---
description: Review code for security, performance, and quality issues
allowed-tools: Read, Grep, Glob, Bash(git:*), LSP
argument-hint: [path|staged]
---

# /review

Review code for security, performance, quality, and production readiness.

## Target
$ARGUMENTS (file, directory, or "staged" for git staged changes - defaults to staged)

## Workflow

1. **Gather context:**
   ```bash
   git diff --cached --name-only          # What files changed
   git diff --cached --stat               # Size of changes
   git log -1 --format="%s" HEAD 2>/dev/null  # Recent commit context
   ```

2. **Quick scans:**
   ```bash
   git diff --cached | grep -E "(TODO|FIXME|XXX|HACK|BUG)"
   git diff --cached | grep -E "(password|secret|api_key|token)" -i
   git diff --cached | grep -E "^\+.*console\.(log|debug)"
   ```

3. **Review each category** (see Focus Areas below)

4. **Report findings by severity:**
   - 🔴 **Critical**: Security vulnerabilities, data loss, breaking changes
   - 🟡 **Medium**: Performance, logic bugs, missing error handling
   - 🟢 **Low**: Style, suggestions, minor improvements

5. **Ask for action:**
   - "Fix critical issues now?"
   - "Create TODO items for medium/low?"
   - "Proceed with commit?"

## Focus Areas

### Security
- Hardcoded credentials, API keys, tokens
- SQL/command injection vectors
- Path traversal vulnerabilities
- Missing auth/authz checks
- Unsafe deserialization
- XSS in user-facing output

### Breaking Changes (API)
- Removed or renamed exports/public methods
- Changed function signatures (params added/removed/reordered)
- Modified return types
- Removed enum values or interface properties
- Changed default values with external impact

**Detection patterns:**
```
# Exports removed
-export (function|class|const|interface) \w+
# Signature changes
-def \w+\([^)]*\)
+def \w+\([^)]*\)  # different params
# Public method changes (C++/Java)
-public \w+ \w+\(
```

### Production Readiness
| Check | What to Look For |
|-------|------------------|
| Error handling | try/catch around external calls, network, file I/O |
| Logging | Key operations logged (not sensitive data) |
| Input validation | User input validated at entry points |
| Edge cases | Null checks, empty arrays, boundary conditions |
| Resource cleanup | Files closed, connections released, memory freed |
| Timeouts | Network calls have timeouts set |
| Graceful degradation | Fallbacks for failures |

**For each new function, verify:**
1. What can fail? Is it handled?
2. What should be logged? Is it?
3. What are the edge cases? Are they covered?

### Code Duplication
- Similar functions across files (>10 lines matching)
- Copy-pasted blocks with minor variations
- Repeated patterns that should be abstracted

**Use grep to find similar patterns:**
```bash
# Find similar function names
git diff --cached | grep -E "^\+.*(function|def|fn) \w+" | sort | uniq -d
```

### Import Hygiene
- Unused imports (added but not used in diff)
- Circular dependency risks (A imports B imports A)
- Missing imports (using symbols not imported)
- Wildcard imports that should be specific

### Logic
- Race conditions (shared state without locks)
- Null/undefined dereferences
- Off-by-one errors in loops
- Missing error handling on async operations
- Incorrect boolean logic

### Performance
- O(n²) or worse in loops
- Allocations inside hot loops
- Missing caching for repeated expensive operations
- Blocking calls on UI/main thread
- N+1 query patterns

### Quality
- Functions > 50 lines → suggest extraction
- Nesting > 4 levels → suggest early returns
- Cyclomatic complexity > 10 → suggest simplification
- Magic numbers without named constants

## Report Format

```markdown
## Review: [target]

### 🔴 Critical
- **file.cpp:42** - Hardcoded API key in source
  Impact: Credentials exposed in version control
  Fix: Move to environment variable

### 🟡 Medium
- **api.ts:156** - Removed `userId` param from `getUser()`
  Impact: Breaking change for callers
  Fix: Add deprecation warning, keep old signature

- **handler.py:89** - No error handling on HTTP request
  Impact: Unhandled exception crashes service
  Fix: Wrap in try/except, log failure, return error response

### 🟢 Low
- **utils.js:23** - Unused import `lodash`
  Fix: Remove import

### ✅ Production Checklist
- [x] Error handling on external calls
- [x] Logging for key operations
- [ ] Input validation at entry points ← **Missing**
- [x] Resource cleanup

### Summary
1 critical, 2 medium, 1 low. Fix critical before commit.
```

## When to Bail
- No staged changes and no path specified
- Files too large to review effectively (>1000 lines)
- Binary or generated files only
- For deep security analysis → use security-reviewer agent

## Should NOT Do
- Auto-fix issues without asking
- Add AI attribution comments
- Review files outside scope
- Nitpick style when logic issues exist
- Block on low-severity issues

## Rules
- Show exact file:line locations
- Explain **impact**, not just what's wrong
- Suggest **specific fixes** with code when helpful
- Prioritize by severity
- If breaking changes found, confirm intent with user
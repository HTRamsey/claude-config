---
description: Review code for security, performance, and quality issues
allowed-tools: Read, Grep, Glob, Bash(git:*), LSP, Task
argument-hint: [--deep] [path|staged]
---

# /review

Review code for security, performance, quality, and production readiness.

## Options
- `--deep` - Spawn 6 specialized review agents in parallel (6x tokens, thorough)
- `--deep security` - Security-focused deep review only
- `--deep performance` - Performance-focused deep review only

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

## Examples

### Review staged changes
```
/review
```

### Review specific file
```
/review src/api/auth.ts
```

### Review entire directory
```
/review src/handlers/
```

## When to Bail
- No staged changes and no path specified
- Files too large to review effectively (>1000 lines)
- Binary or generated files only
- For deep security analysis → use code-reviewer agent

## Should NOT Do
- Auto-fix issues without asking
- Add AI attribution comments
- Review files outside scope
- Nitpick style when logic issues exist
- Block on low-severity issues

## Review Discipline

**Before committing:**
- Run `/review` on staged changes (don't skip "just this once")
- Fix all Critical issues before commit
- Document Medium issues as TODOs if deferring
- Never merge own PR without external review

**During review:**
- Focus on logic and security first, style last
- One concern per comment (actionable, not vague)
- Suggest fixes, not just problems
- If > 10 issues, stop and request smaller PR

**After review:**
- Verify fixes addressed the concern (not just silenced it)
- Re-run review after significant changes
- Document patterns that keep appearing (add to linting)

## Rules
- Show exact file:line locations
- Explain **impact**, not just what's wrong
- Suggest **specific fixes** with code when helpful
- Prioritize by severity
- If breaking changes found, confirm intent with user

## Deep Review Mode (`--deep`)

Spawns 6 specialized review agents in parallel for comprehensive analysis.

### Agents

| Agent | Focus | Key Checks |
|-------|-------|------------|
| **Architecture** | Design patterns, coupling, cohesion | SOLID violations, circular deps, layer violations |
| **Security** | OWASP Top 10, vulnerabilities | Injection, auth bypass, data exposure, secrets |
| **Performance** | Bottlenecks, complexity | O(n²), N+1 queries, memory leaks, blocking calls |
| **Testing** | Coverage, edge cases | Missing tests, weak assertions, flaky patterns |
| **Quality** | Standards, maintainability | Complexity, duplication, naming, dead code |
| **Documentation** | Comments, API docs | Missing docs, outdated comments, unclear APIs |

### Workflow

1. **Gather files** - Same as standard review
2. **Spawn agents** - All 6 in parallel via Task tool
3. **Aggregate** - Combine results, deduplicate findings
4. **Prioritize** - Sort by severity: Critical → High → Medium → Low
5. **Report** - Unified output with agent attribution

### Agent Prompts

Each agent receives:
```
Review the following code for [FOCUS AREA]:
Files: [file list]
Diff: [staged diff or file contents]

Focus specifically on:
- [Key checks for this agent]

Report findings as:
- 🔴 Critical: [description] (file:line)
- 🟡 Medium: [description] (file:line)
- 🟢 Low: [description] (file:line)
```

### Aggregation Rules

1. **Deduplicate** - Same issue from multiple agents → keep most specific
2. **Cross-reference** - Note when multiple agents flag same code
3. **Conflict resolution** - If agents disagree, show both perspectives
4. **Coverage gaps** - Flag files not reviewed by any agent

### Output Format

```markdown
## Deep Review: [target]
**Agents:** 6/6 completed | **Total findings:** X

### 🔴 Critical (X)
- **[file:line]** - [issue] (Architecture, Security)
  Impact: [why it matters]
  Fix: [suggested fix]

### 🟡 Medium (X)
...

### 🟢 Low (X)
...

### Cross-Agent Insights
- [file:line] flagged by 3 agents: Architecture (coupling), Quality (complexity), Testing (coverage)

### Summary
Architecture: 2 issues | Security: 1 critical | Performance: clean | ...
```

### When to Use Deep Review

- Before major releases
- Security-sensitive code changes
- Reviewing unfamiliar codebase
- PR with >500 lines changed
- After significant refactoring

### Cost Consideration

Deep review uses ~6x tokens of standard review. Use for important changes, not routine commits.
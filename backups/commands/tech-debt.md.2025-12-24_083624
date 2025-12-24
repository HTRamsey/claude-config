---
description: Catalog and prioritize technical debt in the codebase
allowed-tools: Read, Grep, Glob, Bash
argument-hint: [path] [--quick]
---

# /tech-debt

## Target
$ARGUMENTS (path to analyze, or empty for current project)

Catalog and prioritize technical debt in the codebase.

## Usage
```
/tech-debt [path]           # Analyze specific path
/tech-debt                  # Analyze current project
/tech-debt --quick          # Fast scan, top issues only
```

## Workflow

### 1. Scan for Debt Indicators
Search for common debt patterns:

```bash
# TODO/FIXME comments
rg -n "TODO|FIXME|HACK|XXX|WORKAROUND" $ARGUMENTS

# Long files (>500 lines)
find . -name "*.py" -o -name "*.ts" -o -name "*.js" | xargs wc -l | sort -rn | head -20

# Complex functions (high cyclomatic complexity indicators)
rg -n "if.*if.*if|else.*else.*else" $ARGUMENTS
```

### 2. Categorize Debt

| Category | Indicators | Impact |
|----------|------------|--------|
| **Code Quality** | Long functions, deep nesting, duplication | Maintainability |
| **Architecture** | Circular deps, god classes, tight coupling | Scalability |
| **Testing** | Missing tests, flaky tests, low coverage | Reliability |
| **Dependencies** | Outdated packages, security vulnerabilities | Security |
| **Documentation** | Missing docs, stale comments | Onboarding |

### 3. Prioritize by Impact

**P1 - Fix Now:**
- Security vulnerabilities
- Data corruption risks
- Blocking other work

**P2 - Fix Soon:**
- Performance bottlenecks
- Frequent bug sources
- High-traffic code paths

**P3 - Fix When Touched:**
- Code smells
- Missing tests
- Outdated patterns

**P4 - Track Only:**
- Nice-to-have improvements
- Style inconsistencies

### 4. Output Format

```markdown
## Technical Debt Report

### P1 - Critical
- [ ] `src/auth.py:45` - SQL injection risk in user query
- [ ] `src/api.py:123` - No input validation on upload endpoint

### P2 - High
- [ ] `src/core/engine.py` - 800 lines, needs decomposition
- [ ] `tests/` - 40% coverage, critical paths untested

### P3 - Medium
- [ ] 15 TODO comments older than 6 months
- [ ] `src/utils/` - 3 files with duplicate helper functions

### P4 - Low
- [ ] Inconsistent naming in `src/models/`
- [ ] Missing docstrings in public API

### Recommended Actions
1. [P1] Security audit of auth module
2. [P2] Extract services from engine.py
3. [P2] Add tests for payment flow
```

## Rules
- Don't fix debt during cataloging
- Focus on impact, not aesthetics
- Track debt in issues/tickets
- Revisit quarterly

## Integration
- Use with `/refactor` to address specific items
- Use with `code-smell-detection` skill for deeper analysis
- Export to GitHub Issues with `gh issue create`

---
description: Quick security scan for common vulnerabilities
allowed-tools: Read, Grep, Glob, Task
argument-hint: [path|staged]
---

# /security

Quick security scan for common vulnerabilities.

## Target
$ARGUMENTS (file, directory, or "staged" - defaults to staged changes)

## Workflow

1. **Determine scope:**
   ```bash
   # For staged changes
   git diff --cached --name-only

   # For path
   find $TARGET -type f \( -name "*.py" -o -name "*.js" -o -name "*.ts" -o -name "*.go" -o -name "*.rs" \)
   ```

2. **Scan for vulnerabilities:**

### Secrets & Credentials
```bash
# Hardcoded secrets
grep -rn "password\s*=\s*['\"]" --include="*.py" --include="*.js"
grep -rn "api_key\s*=\s*['\"]" --include="*.py" --include="*.js"
grep -rn "secret\s*=\s*['\"]" --include="*.py" --include="*.js"

# AWS keys
grep -rn "AKIA[0-9A-Z]{16}" .

# Private keys
grep -rn "BEGIN.*PRIVATE KEY" .
```

### Injection Vulnerabilities
```bash
# SQL injection risks (string formatting in queries)
grep -rn "execute.*%s\|execute.*f\"\|execute.*\.format" --include="*.py"
grep -rn "query.*\+.*req\.\|query.*\${" --include="*.js" --include="*.ts"

# Command injection
grep -rn "subprocess.*shell=True\|os\.system\|eval(" --include="*.py"
grep -rn "child_process\.exec\|eval(" --include="*.js" --include="*.ts"
```

### Input Validation
```bash
# Unvalidated user input
grep -rn "request\.get\|request\.post\|req\.body\|req\.params" --include="*.py" --include="*.js"
```

### Path Traversal
```bash
# Path operations with user input
grep -rn "open(.*request\|path\.join.*req\|readFile.*req" .
```

3. **Check dependencies:**
   ```bash
   # Python
   [ -f requirements.txt ] && pip-audit 2>/dev/null || echo "pip-audit not installed"

   # Node.js
   [ -f package.json ] && npm audit --json 2>/dev/null | jq '.vulnerabilities | keys[]' || echo "No npm audit"

   # Rust
   [ -f Cargo.toml ] && cargo audit 2>/dev/null || echo "cargo-audit not installed"
   ```

4. **Report findings:**

## Output Format

```markdown
## Security Scan: <target>

### 🔴 Critical
- **<vulnerability>** - `file:line`
  - Risk: <impact>
  - Fix: <recommendation>

### 🟡 Warning
- **<issue>** - `file:line`
  - Risk: <impact>
  - Fix: <recommendation>

### ✅ Passed Checks
- No hardcoded secrets detected
- No obvious SQL injection patterns
- Dependencies up to date

### Recommendations
1. <action item>
2. <action item>
```

## Quick Checks Summary

| Category | Pattern | Risk |
|----------|---------|------|
| Secrets | Hardcoded passwords/keys | Critical |
| SQL Injection | String formatting in queries | Critical |
| Command Injection | shell=True, eval() | Critical |
| XSS | Unescaped user input in HTML | High |
| Path Traversal | User input in file paths | High |
| Dependencies | Known vulnerable versions | Varies |

## Rules
- Report severity accurately
- Include file:line references
- Suggest specific fixes
- Don't claim "secure" - claim "no issues found"
- For deep analysis, use `/deep-review` instead

## For Comprehensive Security Review
Use `Task` with `security-reviewer` agent or run `/deep-review` for parallel specialist analysis.

---
name: security-audit
description: Use when reviewing code for security vulnerabilities, before releases, or when handling sensitive data. Covers vulnerability auditing (OWASP Top 10, STRIDE) and defensive implementation (multi-layer validation to make bugs structurally impossible).
---

# Security Audit Skill

**Persona:** Paranoid security engineer who assumes all input is malicious and assumes every layer will receive bad data - trust nothing, verify everything.

## Should NOT Attempt

- Certify code as "secure" (can only identify known issues)
- Skip STRIDE analysis on auth/data features
- Approve code with obvious injection vectors
- Ignore dependency vulnerabilities
- Review without checking OWASP Top 10
- Validate only at entry point ("the caller checked it")
- Trust internal function parameters without re-validation
- Skip validation for "performance" without measurement
- Add validation without corresponding tests

## Checklist

| Category | Checks |
|----------|--------|
| **Input Validation** | All external input validated, length limits, type checking, whitelist over blacklist |
| **Injection** | SQL: parameterized queries, Command: no shell interpolation, Path: no traversal, XSS: output encoding |
| **Auth/Authz** | Auth on all sensitive endpoints, secure session mgmt, privilege checks, no hardcoded creds |
| **Data Protection** | Encrypted at rest, TLS in transit, no secrets in logs, secure deletion |
| **Error Handling** | No stack traces to users, generic messages, all errors logged securely, fail secure |
| **Dependencies** | Known vulns checked, minimal deps, pinned versions |
| **Multi-Layer Validation** | Validation at entry, business logic, environment guards, debug instrumentation |

## Multi-Layer Validation Strategy

**Core Principle:** Validate at EVERY layer data passes through. Make bugs structurally impossible.

**Single validation:** "We fixed the bug"
**Multiple layers:** "We made the bug impossible"

### The Four Validation Layers

| Layer | Purpose | Example |
|-------|---------|---------|
| 1. Entry Point | Reject invalid input at API boundary | Check not empty, exists, is directory |
| 2. Business Logic | Data makes sense for operation | Validate required fields for this action |
| 3. Environment Guards | Prevent danger in specific contexts | Refuse git init outside tmpdir in tests |
| 4. Debug Instrumentation | Capture context for forensics | Log directory, cwd, stack before risky ops |

### Implementation Pattern

```typescript
// Layer 1: Entry validation
function createProject(name: string, dir: string) {
  if (!dir?.trim()) throw new Error('dir cannot be empty');
  if (!existsSync(dir)) throw new Error(`dir not found: ${dir}`);
}

// Layer 2: Business logic
function initWorkspace(projectDir: string) {
  if (!projectDir) throw new Error('projectDir required');
}

// Layer 3: Environment guard
async function gitInit(dir: string) {
  if (process.env.NODE_ENV === 'test' && !dir.startsWith(tmpdir())) {
    throw new Error(`Refusing git init outside temp: ${dir}`);
  }
}

// Layer 4: Debug instrumentation
logger.debug('About to git init', { dir, cwd: process.cwd(), stack: new Error().stack });
```

### Multi-Layer Examples

**SQL Injection via User Input:**
- Layer 1 (API): Validate username against regex `^[a-zA-Z0-9_]+$`
- Layer 2 (Business): Parameterized query regardless of input
- Layer 3 (Database): User has minimal permissions
- Layer 4 (Audit): Log all queries with parameters

**File Path Traversal:**
- Layer 1 (API): Reject paths containing `..`
- Layer 2 (Business): `path.resolve()` then verify starts with allowed directory
- Layer 3 (Environment): Chroot/container isolation
- Layer 4 (Monitor): Alert on any path resolution outside allowed directories

**Empty String Causes Crash:**
- Layer 1 (API): `if (!path?.trim()) throw new Error('path required')`
- Layer 2 (Business): `if (!isAbsolute(path)) throw new Error('absolute path required')`
- Layer 3 (Environment): `if (NODE_ENV === 'test' && !path.startsWith(tmpdir())) throw`
- Layer 4 (Debug): `logger.debug('git init', { path, cwd, stack })`

### When to Apply Defense-in-Depth

When you find a bug caused by invalid data:
1. **Trace data flow** - Where does bad value originate?
2. **Map checkpoints** - Every point data passes through
3. **Add validation at each layer**
4. **Test each layer** - Bypass layer 1, verify layer 2 catches it

### Escalation Triggers (Multi-Layer)

| Condition | Action |
|-----------|--------|
| Invalid data crosses >3 layers undetected | Architecture review needed |
| Same invalid data pattern recurs | Add type-level constraint (branded types, enums) |
| Validation logic duplicated across layers | Extract to shared validator module |
| Performance impact >5% from validation | Profile and optimize hot paths only |

## Search Patterns
```bash
rg "eval\(|exec\(|system\(|popen\(" --type cpp  # dangerous functions
rg "password|secret|key|token" -i               # credentials
rg "TODO|FIXME|HACK|XXX"                        # incomplete code
rg "http://"                                    # non-HTTPS
```

## STRIDE Threat Modeling

| Threat | Question | Mitigations |
|--------|----------|-------------|
| **S**poofing | Can attacker impersonate? | Strong auth, MFA, signed tokens |
| **T**ampering | Can attacker modify data? | Integrity checks, HMAC, signatures |
| **R**epudiation | Can attacker deny actions? | Audit logs, timestamps |
| **I**nfo Disclosure | Can attacker access data? | Encryption, access control |
| **D**enial of Service | Can attacker overwhelm? | Rate limiting, redundancy |
| **E**levation of Privilege | Can attacker escalate? | Least privilege, sandboxing |

**Apply STRIDE to:** User data features, auth changes, external APIs, file upload/download, admin operations

## OWASP Top 10 Reference

| # | Vulnerability | Key Checks |
|---|---------------|------------|
| A01 | Broken Access Control | Auth on all endpoints, RBAC |
| A02 | Cryptographic Failures | No weak crypto, encrypt sensitive data |
| A03 | Injection | Parameterized queries, no shell interpolation |
| A04 | Insecure Design | Threat modeling, secure defaults |
| A05 | Security Misconfiguration | No debug in prod, minimal permissions |
| A06 | Vulnerable Components | Dependency audit, pinned versions |
| A07 | Auth Failures | Strong passwords, session management |
| A08 | Data Integrity Failures | Signed updates, verify integrity |
| A09 | Logging Failures | Log security events, no sensitive data in logs |
| A10 | SSRF | Validate URLs, allowlist destinations |

## Escalation Triggers

| Situation | Escalate To |
|-----------|-------------|
| Critical vulnerability found | Immediate user notification, suggest fix |
| Threat model needed for complex feature | `security-reviewer` agent for STRIDE analysis |
| Crypto/auth implementation | Flag for expert human review |
| Dependency with known CVE | `migration-planner` agent for remediation |
| Production incident suspected | `devops-troubleshooter` agent |

## Failure Behavior

- **Cannot assess risk:** Report what's unclear, request more context
- **Vulnerability confirmed:** Rate severity (Critical/High/Medium/Low), suggest remediation
- **Uncertain if exploitable:** Document concern, recommend defensive fix anyway
- **Too many issues found:** Prioritize by severity, recommend fixing critical first

## Integration

- **security-reviewer** agent - Automated security review
- **code-reviewer** agent - Security is one aspect of reviews
- **systematic-debugging** skill - Debugging workflow when security bugs found
- **test-driven-development** skill - Verify each validation layer with tests

## Key Insight

All four validation layers are necessary. During testing, each layer catches bugs others miss:
- Different code paths bypass entry validation
- Mocks bypass business logic
- Edge cases need environment guards
- Debug logging identifies structural misuse

**Don't stop at one validation point.**

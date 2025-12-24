---
name: security-audit
description: Use when reviewing code for security vulnerabilities, before releases, or when handling sensitive data. Triggers on auth changes, user input handling, API endpoints. Covers OWASP Top 10 and STRIDE threat modeling.
---

# Security Audit Skill

**Persona:** Paranoid security engineer who assumes all input is malicious.

## Should NOT Attempt

- Certify code as "secure" (can only identify known issues)
- Skip STRIDE analysis on auth/data features
- Approve code with obvious injection vectors
- Ignore dependency vulnerabilities
- Review without checking OWASP Top 10

## Checklist

| Category | Checks |
|----------|--------|
| **Input Validation** | All external input validated, length limits, type checking, whitelist over blacklist |
| **Injection** | SQL: parameterized queries, Command: no shell interpolation, Path: no traversal, XSS: output encoding |
| **Auth/Authz** | Auth on all sensitive endpoints, secure session mgmt, privilege checks, no hardcoded creds |
| **Data Protection** | Encrypted at rest, TLS in transit, no secrets in logs, secure deletion |
| **Error Handling** | No stack traces to users, generic messages, all errors logged securely, fail secure |
| **Dependencies** | Known vulns checked, minimal deps, pinned versions |

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
| Threat model needed for complex feature | `threat-modeling-expert` agent |
| Crypto/auth implementation | Flag for expert human review |
| Dependency with known CVE | `dependency-auditor` agent |
| Production incident suspected | `incident-responder` agent |

## Failure Behavior

- **Cannot assess risk:** Report what's unclear, request more context
- **Vulnerability confirmed:** Rate severity (Critical/High/Medium/Low), suggest remediation
- **Uncertain if exploitable:** Document concern, recommend defensive fix anyway
- **Too many issues found:** Prioritize by severity, recommend fixing critical first

## Integration

- **security-reviewer** (agent) - Automated security review
- **giving-code-review** - Security is one aspect of reviews
- **error-handling-patterns** - Secure error handling

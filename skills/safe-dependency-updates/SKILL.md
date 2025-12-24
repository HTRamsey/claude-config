---
name: safe-dependency-updates
description: Use when updating dependencies, responding to security advisories, or managing package versions - systematic approach to minimize risk
---

# Safe Dependency Updates

**Persona:** Cautious maintainer who treats every dependency update as a potential breaking change.

**Core principle:** Update proactively and incrementally. Emergency updates are stressful and risky.

## Should NOT Attempt

- Update all dependencies at once (batch patches only)
- Force-resolve peer dependency warnings without understanding
- Skip reading changelogs for major version bumps
- Update production deps without running full test suite
- Downgrade lockfile versions without explicit request

## Update Categories

| Category | Risk | Frequency | Process |
|----------|------|-----------|---------|
| Patch (1.2.3 -> 1.2.4) | Low | Weekly | Batch update |
| Minor (1.2.x -> 1.3.0) | Medium | Monthly | One at a time |
| Major (1.x -> 2.0) | High | Quarterly | Dedicated effort |
| Security | Varies | Immediately | Priority handling |

## Pre-Update Checklist

- [ ] Read CHANGELOG for version range
- [ ] Check for breaking changes
- [ ] Review GitHub issues for known problems
- [ ] Verify test coverage is adequate
- [ ] Ensure CI is green before starting

## Update Process

### 1. Audit Current State
```bash
npm audit / pip-audit / cargo audit / bundle audit  # vulnerabilities
npm outdated / pip list --outdated                   # outdated packages
```

### 2. Update Incrementally
```bash
# BAD: npm update (all at once)
# GOOD: One at a time
npm install <package>@<version> && npm test && git commit -m "Update <package> to <version>"
```

### 3. Test Thoroughly
- Run full test suite + integration tests
- Manual smoke test critical paths
- Check for deprecation warnings: `npm test 2>&1 | grep -i deprecat`

## Major Version Upgrades

Treat as a mini-project:
1. Create branch: `feature/upgrade-react-18`
2. Read migration guide
3. Update package, fix breaking changes one file at a time
4. Run tests, fix failures
5. Test manually, deploy to staging
6. Monitor after deploy

## Security Updates

| Severity | Response Time | Process |
|----------|---------------|---------|
| Critical | Hours | Direct to production (with tests) |
| High | 1-2 days | Normal PR, expedited review |
| Medium | 1 week | Normal PR |
| Low | Next maintenance window | Batch with others |

```bash
npm audit                                    # Identify
grep -r "_.merge\|_.defaultsDeep" src/       # Check if exploitable
npm install lodash@4.17.21 && npm test       # Update + test
git checkout -b security/lodash-CVE-2021-23337  # Focused PR
```

## Lockfile Management

Always commit lockfiles: `package-lock.json`, `yarn.lock`, `Pipfile.lock`, `poetry.lock`, `Cargo.lock`, `Gemfile.lock`

Rollback: `git checkout HEAD~1 -- package-lock.json && npm ci`

## Pinning Strategy

| Prefix | Meaning | Use When |
|--------|---------|----------|
| None | Exact version | Critical deps |
| `~` | Patch updates | Stable deps |
| `^` | Minor updates | Active deps, trust maintainer |

## Red Flags

- Updating all deps at once
- Skipping tests after update
- Ignoring deprecation warnings
- Not reading changelogs for major versions
- Force-resolving peer dependency warnings

## Rollback Plan

```bash
git checkout HEAD~1 -- package-lock.json && npm ci
# Investigate: error logs, version comparison, missed breaking changes
```

## Escalation Triggers

| Situation | Escalate To |
|-----------|-------------|
| Breaking change affects >5 files | Create dedicated branch, ask user |
| Peer dependency conflict unresolvable | Ask user for guidance |
| Security vulnerability in direct dep with no patch | `security-reviewer` agent |
| Major framework upgrade (React, Angular, etc.) | Plan as mini-project |

## Failure Behavior

- **Tests fail after update:** Roll back immediately, report which package broke tests
- **Audit shows unfixable CVE:** Report severity, suggest workarounds or alternatives
- **Conflicting peer deps:** Report conflict tree, don't force-resolve
- **Build fails:** Report error, suggest checking package compatibility matrix

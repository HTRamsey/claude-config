# Skill, Agent & Command Usage

## Before Creating Configuration Files

| Creating | Must Use |
|----------|----------|
| Hook (`~/.claude/hooks/*.py`) | `hook-creator` skill |
| Agent (`~/.claude/agents/*.md`) | `agent-creator` skill |
| Command (`~/.claude/commands/*.md`) | `command-creator` skill |
| Skill (`~/.claude/skills/*/SKILL.md`) | `skill-creator` skill |

## Slash Commands

| Task | Command |
|------|---------|
| Commit changes | `/commit` |
| Review code | `/review` |
| Run tests | `/test` |
| Debug issues | `/debug` |
| Implement feature | `/implement` |
| Refactor safely | `/refactor` |
| Generate docs | `/docs` |
| Create PR | `/pr` |
| Fix CI | `/ci-fix` |
| Track tech debt | `/tech-debt` |
| Save checkpoint | `/checkpoint` |
| Git worktree | `/worktree` |
| Task queue | `/queue` |
| Claude flow | `/flow` |

## Skills (16)

### Core Workflows
| Trigger | Skill |
|---------|-------|
| Bug, test failure, unexpected behavior | `systematic-debugging` |
| Writing new feature/bugfix, adding tests | `test-driven-development` |
| About to claim "done" or "fixed" | `verification-before-completion` |
| Security review, vulnerability audit | `security-audit` |

### Quality & Process
| Trigger | Skill |
|---------|-------|
| Before refactoring, complexity increases | `code-smell-detection` |
| Received code review feedback | `receiving-code-review` |
| Context bloated, before complex task | `context-management` |
| 3+ similar operations | `batch-operations` |
| 3+ independent issues to investigate | `subagent-driven-development` |

### Git & Implementation
| Trigger | Skill |
|---------|-------|
| Feature needs isolation | `using-git-worktrees` |
| Multi-day feature, avoid long branches | `incremental-implementation` |

### Specialized
| Trigger | Skill |
|---------|-------|
| Memory leaks, profiling, allocation issues | `memory-management-optimization` |

### Creators
| Trigger | Skill |
|---------|-------|
| Creating hooks | `hook-creator` |
| Creating agents | `agent-creator` |
| Creating commands | `command-creator` |
| Creating skills | `skill-creator` |

## Agents (23 custom + 3 built-in)

### Built-in Agents (no file needed)
| Trigger | Agent |
|---------|-------|
| Codebase exploration | `Explore` |
| Implementation planning | `Plan` |
| Claude Code/SDK questions | `claude-code-guide` |

### Quick Lookups (Haiku)
| Trigger | Agent |
|---------|-------|
| "What is X?", "Where is X defined?" | `quick-lookup` |
| "What does this error mean?" | `error-explainer` |

### Research
| Trigger | Agent |
|---------|-------|
| Deep research, comparisons, migrations | `technical-researcher` |

### Code Review & Quality
| Trigger | Agent |
|---------|-------|
| Code review (security, perf, a11y, dead code) | `code-reviewer` |
| Security-focused review, threat modeling | `security-reviewer` |

### Generation & Planning
| Trigger | Agent |
|---------|-------|
| Adding tests, increasing coverage | `test-generator` |
| API docs, README updates | `doc-generator` |
| Multi-specialist coordination, planning | `orchestrator` |

### Analysis
| Trigger | Agent |
|---------|-------|
| Dependencies, CVEs, version upgrades | `migration-planner` |

### Architecture
| Trigger | Agent |
|---------|-------|
| Backend system design, API design | `backend-architect` |
| Database strategy, schema, optimization | `database-architect` |
| LLM integration, RAG, prompt engineering | `ai-engineer` |

### Operations
| Trigger | Agent |
|---------|-------|
| CI/CD, builds, deployment, observability | `devops-troubleshooter` |
| Production incidents, outage triage | `incident-responder` |

### Specialized
| Trigger | Agent |
|---------|-------|
| Complex git ops, history, merge conflicts | `git-expert` |
| C++, Qt, embedded systems | `cpp-expert` |
| Context bloated | `context-optimizer` |
| Similar changes across 3+ files | `batch-editor` |
| Test failures, flaky tests, timing issues | `testing-debugger` |
| Platform-specific bugs | `cross-platform-tester` |
| Import cleanup, circular deps | `import-optimizer` |
| Binary protocols, serial, MAVLink | `protocol-analyzer` |
| Timing, latency, real-time issues | `real-time-systems` |

## Key Workflows

**Before claiming work is done:**
1. Use `Skill(verification-before-completion)`
2. Run actual verification commands
3. Show evidence of success

**Before complex debugging:**
1. Use `Skill(systematic-debugging)`
2. Follow the four-phase framework
3. Understand before fixing

**Before creating config files:**
1. Load the appropriate creator skill
2. Follow the skill's process

# Mandatory Skill, Agent & Command Usage

## CRITICAL: Forced Evaluation Protocol

Before ANY implementation task, you MUST follow this protocol:

**Step 1 - EVALUATE**: Review skill categories below. State YES/NO for each relevant category.
**Step 2 - ACTIVATE**: Use `Skill()` tool for all YES skills BEFORE writing code.
**Step 3 - IMPLEMENT**: Only after activation proceed with implementation.

Skipping evaluation makes work INCOMPLETE. This protocol is MANDATORY.

## Before Creating Configuration Files

| Creating | Must Use |
|----------|----------|
| Hook (`~/.claude/hooks/*.py`) | `hook-creator` skill |
| Agent (`~/.claude/agents/*.md`) | `agent-creator` skill |
| Command (`~/.claude/commands/*.md`) | `command-creator` skill |
| Skill (`~/.claude/skills/*/SKILL.md`) | `skill-creator` skill |

## Slash Commands - Use These First

| Task | Command | When |
|------|---------|------|
| Commit changes | `/commit` | Before any git commit |
| Review code | `/review` | After significant changes, before commits |
| Run tests | `/test` | When tests fail or need diagnosis |
| Refactor | `/refactor` | Before any refactoring work |
| Generate docs | `/docs` | When documentation needed |
| Track tech debt | `/tech-debt` | When cataloging issues |
| Implement feature | `/implement` | For structured feature work |
| Save checkpoint | `/checkpoint` | Before complex or risky work |
| Git worktree | `/worktree` | For parallel development |
| Task queue | `/queue` | Add/run background agent tasks |
| Claude flow | `/flow` | Multi-agent workflow orchestration |
| Summarize session | `/summarize` | End of session recap |
| Debug issues | `/debug` | Systematic debugging with root cause |
| Create PR | `/pr` | Well-structured pull request |
| Fix CI | `/ci-fix` | Fix CI failures iteratively |
| Pipeline | `/pipeline` | Multi-stage feature workflow |

## Skills - Load Before These Tasks

### Development Workflows
| Trigger | Skill |
|---------|-------|
| Bug, test failure, unexpected behavior | `systematic-debugging` |
| Writing new feature/bugfix | `test-driven-development` |
| Multi-day feature, avoid long branches | `incremental-implementation` |
| About to claim "done" or "fixed" | `verification-before-completion` |
| Creating, developing, before code | `brainstorming` |

### Code Quality
| Trigger | Skill |
|---------|-------|
| Before refactoring, complexity increases | `code-smell-detection` |
| Writing/changing tests, adding mocks | `testing-anti-patterns` |
| Implementing error handling | `error-handling-patterns` |
| Invalid data failures, multi-layer validation | `defense-in-depth` |
| Reviewing PRs, giving feedback | `giving-code-review` |
| Received code review feedback | `receiving-code-review` |
| Before merging, verify requirements | `requesting-code-review` |

### Architecture & Design
| Trigger | Skill |
|---------|-------|
| Architectural choices, library selection | `architecture-decision-records` |
| Designing APIs, breaking changes | `api-versioning` |
| Controlled rollout, trunk-based dev | `feature-flag-patterns` |
| Changing database schema | `database-migrations` |
| Adding logging, debugging distributed | `observability-logging` |

### Efficiency
| Trigger | Skill |
|---------|-------|
| Codebase exploration | `efficient-search` |
| 3+ similar operations | `batch-operations` |
| Context bloated, before complex task | `context-management` |
| Files over 200 lines, large logs | `large-file-handling` |
| 3+ independent issues | `subagent-driven-development` |

### Process
| Trigger | Skill |
|---------|-------|
| Need detailed implementation tasks | `writing-plans` |
| Partner provides implementation plan | `executing-plans` |
| Feature needs isolation | `using-git-worktrees` |
| Implementation complete, integrate work | `finishing-a-development-branch` |
| Updating dependencies, CVEs | `safe-dependency-updates` |

### Specialized
| Trigger | Skill |
|---------|-------|
| Performance optimization | `optimize` |
| Code migration, upgrades | `migrate` |
| Security review | `security-audit` |
| Errors deep in execution | `root-cause-tracing` |
| Race conditions, timing issues | `condition-based-waiting` |

## Agents - Use via Task Tool

### Quick Lookups (Haiku - 10x cheaper)
| Trigger | Agent |
|---------|-------|
| "What is X?", "Where is X defined?" | `quick-lookup` |
| "What does this error mean?" | `error-explainer` |
| Simple lookup, quick syntax | `quick-researcher` |
| Claude Code/SDK questions | `claude-code-guide` |

### Research
| Trigger | Agent |
|---------|-------|
| Deep research, comparisons, migrations | `technical-researcher` |

### Code Review & Quality
| Trigger | Agent |
|---------|-------|
| After significant changes, before commits | `code-reviewer` |
| Auth code, security-sensitive releases | `security-reviewer` |
| Performance issues, hot paths | `perf-reviewer` |
| UI components, forms, WCAG | `accessibility-reviewer` |

### Generation & Planning
| Trigger | Agent |
|---------|-------|
| Adding tests, increasing coverage | `test-generator` |
| API docs, README updates | `doc-generator` |
| Designing new APIs, endpoints | `api-designer` |
| Planning large refactors | `refactoring-planner` |
| Multi-specialist coordination | `orchestrator` |

### Analysis
| Trigger | Agent |
|---------|-------|
| Find unused code, before cleanup | `dead-code-finder` |
| Dependencies, CVEs, version upgrades | `migration-planner` |
| Optimization ROI, business case | `impact-analyzer` |
| Build failures, compilation issues | `build-expert` |

### Architecture (Opus)
| Trigger | Agent |
|---------|-------|
| Backend system design, microservices | `backend-architect` |
| Database strategy, schema, optimization | `database-architect` |
| LLM integration, RAG, embeddings | `ai-engineer` |
| Security threat analysis, attack surface | `threat-modeling-expert` |

### Operations (Sonnet)
| Trigger | Agent |
|---------|-------|
| CI/CD failures, deployment issues | `devops-troubleshooter` |
| Production incidents, outage triage | `incident-responder` |
| Metrics, logging, tracing design | `observability-engineer` |

### Specialized
| Trigger | Agent |
|---------|-------|
| Complex git ops, history, merge conflicts | `git-expert` |
| C++, Qt, embedded systems | `cpp-expert` |
| Context bloated | `context-optimizer` |
| Similar changes across 3+ files | `batch-editor` |
| Test failures, flaky tests, timing issues | `testing-debugger` |

## Enforcement

**MANDATORY: Follow the Forced Evaluation Protocol (top of file) for ALL implementation tasks.**

**Before creating hooks/agents/commands/skills:**
1. STOP - Don't write directly
2. Load the appropriate creator skill
3. Follow the skill's process

**Before claiming work is done:**
1. EVALUATE: Is `verification-before-completion` needed? → YES for any completion claim
2. ACTIVATE: Use `Skill(verification-before-completion)`
3. Run actual verification commands
4. Show evidence of success

**Before complex debugging:**
1. EVALUATE: Is `systematic-debugging` needed? → YES for any non-trivial bug
2. ACTIVATE: Use `Skill(systematic-debugging)`
3. Follow the four-phase framework
4. Understand before fixing

**Before writing tests:**
1. EVALUATE: Is `testing-anti-patterns` needed? → YES when adding mocks or test code
2. ACTIVATE: Use `Skill(testing-anti-patterns)`
3. Avoid testing mock behavior, production pollution

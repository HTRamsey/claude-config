# Reference

Skills, agents, and commands quick reference.

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
| Lint changes | `/lint` |
| Refactor safely | `/refactor` |
| Generate docs | `/docs` |
| Create PR | `/pr` |
| Fix CI | `/ci-fix` |
| Track tech debt | `/tech-debt` |
| Generate changelog | `/changelog` |
| Audit config | `/config-audit` |
| Quick health check | `/status` |
| Save checkpoint | `/checkpoint` |
| Git worktree | `/worktree` |
| Task queue | `/queue` |
| Claude flow | `/flow` |

**Task Queue**: `/queue add "task" --agent TYPE` | `/queue daemon start|stop`
**Orchestration**: `/flow <workflow> "objective"` (feature, security-review, refactor, quick-review, docs)

### Built-in Commands
| Task | Command |
|------|---------|
| Clear context | `/clear` |
| Compact context | `/compact` |
| Rewind conversation | `/rewind` |
| Rename session | `/rename` |
| Get help | `/help` |
| Show cost | `/cost` |
| Diagnose issues | `/doctor` |
| Switch model | `/model` |
| Manage permissions | `/permissions` |
| Resume session | `/resume` |
| Add directory | `/add-dir` |
| Manage MCP servers | `/mcp` |
| View tasks | `/tasks` |
| Login/Logout | `/login`, `/logout` |

## Skills

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

## Agents

**Invocation methods:**
- `Task(subagent_type="agent-name", prompt="...")` - programmatic
- `@agent-name` in prompt - inline mention (Tab to accept suggestion)

### Built-in (no file needed)
| Trigger | Agent |
|---------|-------|
| Codebase exploration | `Explore` |
| Implementation planning | `Plan` |
| Claude Code/SDK questions | `claude-code-guide` |

### Quick Lookups (Haiku)
| Trigger | Agent |
|---------|-------|
| "What is X?", "Where is X defined?", "What does this error mean?" | `quick-lookup` |

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
| CI/CD, builds, deployment, incidents, observability | `devops-troubleshooter` |

### Specialized
| Trigger | Agent |
|---------|-------|
| Complex git ops, history, merge conflicts | `git-expert` |
| Modern C++, embedded, performance, CMake | `cpp-expert` |
| Qt/QML, signals/slots, threading, Model/View | `qt-qml-expert` |
| Context bloated | `context-optimizer` |
| Similar changes across 3+ files | `batch-editor` |
| Test failures, flaky tests, timing issues | `testing-debugger` |
| Platform-specific bugs | `cross-platform-tester` |
| MAVLink, ArduPilot, PX4, QGroundControl | `mavlink-expert` |

### Meta (Config Management)
| Trigger | Agent |
|---------|-------|
| Audit/improve ~/.claude config, research Claude Code updates | `claude-config-expert` |

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

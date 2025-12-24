# Claude Code Configuration

Personal Claude Code configuration with custom agents, commands, hooks, skills, and scripts.

## Structure

```
~/.claude/
├── CLAUDE.md           # Entry point, references rules
├── settings.json       # Permissions, model config, hooks
├── requirements.txt    # Python deps for hooks (tiktoken)
├── rules/              # Auto-loaded instruction files
├── agents/             # Task tool subagent definitions
├── commands/           # Slash command definitions
├── hooks/              # Event-triggered Python scripts
├── skills/             # Loaded-on-demand workflows
├── scripts/            # Shell utility scripts
└── output-styles/      # Custom output formats
```

## Quick Start

1. Clone to `~/.claude/`:
   ```bash
   git clone <repo-url> ~/.claude
   ```

2. Set up Python environment for hooks:
   ```bash
   cd ~/.claude
   python3 -m venv venv
   ./venv/bin/pip install -r requirements.txt
   ```

3. Restart Claude Code to pick up configuration.

## Components

### Rules (auto-loaded)
- `00-quickstart.md` - 5-min onboarding
- `01-style.md` - Communication & code style
- `02-security.md` - Security & verification
- `03-optimization.md` - Tool & output optimization
- `04-skills.md` - Skill/agent/command triggers
- `05-context.md` - Hooks & context management

### Key Agents
| Agent | Model | Purpose |
|-------|-------|---------|
| `quick-lookup` | Haiku | Single fact retrieval |
| `code-reviewer` | Opus | Comprehensive code review |
| `security-reviewer` | Opus | Security-focused review |
| `flaky-test-fixer` | Sonnet | Debug timing/race issues in tests |
| `qt-expert` | Sonnet | Qt/QML patterns and debugging |

### Key Commands
| Command | Purpose |
|---------|---------|
| `/review` | Pre-commit quality review |
| `/commit` | Create formatted commit |
| `/test` | Diagnose test failures |
| `/implement` | Structured feature work |

### Key Skills
| Skill | Purpose |
|-------|---------|
| `systematic-debugging` | 4-phase debugging framework |
| `concurrency-debugging` | Race conditions, deadlocks |
| `test-driven-development` | TDD workflow |

## Health Check

```bash
~/.claude/scripts/health-check.sh
```

## License

Personal configuration. Use at your own risk.

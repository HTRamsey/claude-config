# Multi-LLM Instructions (Tier 2)

Route tasks to the optimal LLM provider based on task characteristics.

## Routing Table

| Pattern | Provider | Reason |
|---------|----------|--------|
| Large files (>100KB) | `gemini` | 1M token context |
| Whole codebase analysis | `gemini` | Large context |
| Boilerplate/CRUD/templates | `codex` | Cheaper, optimized |
| Scaffolding new project | `codex` | Fast generation |
| Architecture decisions | `claude` | Best reasoning |
| Security review | `claude` | Deep analysis |
| Debugging complex issues | `claude` | Step-by-step |
| Code review | `claude` | Nuanced feedback |
| Default | `claude` | Primary tool |

## Delegation Commands

```bash
# Manual routing (user runs in terminal)
~/.claude/scripts/automation/llm-route.sh "task description"
~/.claude/scripts/automation/llm-route.sh -p gemini "task"

# Delegate from Claude via tmux
~/.claude/scripts/automation/llm-delegate.sh gemini "summarize this 500KB log"
~/.claude/scripts/automation/llm-delegate.sh codex "generate REST API for User model"

# Pipe large content
cat large-file.log | ~/.claude/scripts/automation/llm-delegate.sh gemini "summarize"
```

## When to Delegate

1. **Context too large** - File or content exceeds comfortable context
2. **Boilerplate task** - Generating repetitive code patterns
3. **Cost optimization** - Simple task doesn't need Opus reasoning

## Should NOT Delegate

- Security-sensitive code review
- Architectural decisions
- Complex debugging requiring reasoning
- Tasks requiring project context already loaded

## Delegation Flow

1. Identify task matches delegation pattern
2. Announce: "This is a large file, delegating to Gemini..."
3. Run: `llm-delegate.sh <provider> "<prompt>"`
4. Capture and present result to user
5. Optionally refine with Claude's analysis

## Escalate When

- Provider CLI not installed
- Delegation times out
- Response quality is poor
- Task requires Claude-specific context

For advanced configuration and provider setup, see SKILL.md.

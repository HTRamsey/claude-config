---
name: multi-llm
description: Route tasks to optimal LLM provider (Gemini, Codex, Claude)
---

# Multi-LLM Orchestration

Route tasks to the optimal LLM provider for cost efficiency and capability matching.

## Overview

Different LLMs excel at different tasks. This skill enables intelligent routing:
- **Gemini**: 1M+ token context for large file analysis
- **Codex**: Optimized for code generation, cheaper for boilerplate
- **Copilot**: IDE-integrated quick edits
- **Claude**: Best reasoning, architecture, security analysis

## Provider Capabilities

### Gemini (`gemini-cli`)
- **Context**: 1M+ tokens
- **Best for**: Large file analysis, whole codebase questions, long documents
- **Cost**: Competitive for large context
- **Limitations**: Less nuanced reasoning than Claude

### Codex (`codex-cli`)
- **Context**: Moderate
- **Best for**: Code generation, CRUD, boilerplate, templates
- **Cost**: Lower than Claude for generation tasks
- **Limitations**: Less architectural understanding

### Copilot (`gh copilot suggest`)
- **Context**: Limited
- **Best for**: Quick inline suggestions, IDE integration
- **Cost**: Included with GitHub subscription
- **Limitations**: Not designed for complex tasks

### Claude (`claude`)
- **Context**: 200K tokens (Opus/Sonnet)
- **Best for**: Architecture, security, debugging, code review, reasoning
- **Cost**: Premium for complex tasks
- **Limitations**: Smaller context than Gemini

## Routing Decision Tree

```
Task received
    │
    ├─ Input > 100KB? ─────────────────────────→ gemini
    │
    ├─ Whole codebase question? ───────────────→ gemini
    │
    ├─ Boilerplate/CRUD/scaffold pattern? ─────→ codex
    │
    ├─ Security/architecture/debugging? ───────→ claude
    │
    └─ Default ────────────────────────────────→ claude
```

## Scripts

### llm-route.sh - Manual CLI Switching

For users to manually route tasks from terminal:

```bash
# Auto-detect best provider
llm-route.sh "analyze this large log file"

# Force specific provider
llm-route.sh -p gemini "summarize this"

# With file input
llm-route.sh -f large.log "what errors occurred?"

# List available providers
llm-route.sh --list
```

### llm-delegate.sh - Claude-Initiated Delegation

For Claude to delegate tasks via tmux:

```bash
# Basic delegation
llm-delegate.sh gemini "summarize this 500KB log"

# With timeout
llm-delegate.sh -t 180 gemini "analyze entire codebase"

# Pipe content
cat large.log | llm-delegate.sh gemini "summarize errors"

# Keep tmux session for inspection
llm-delegate.sh -k codex "generate User CRUD"
```

## Configuration

### Environment Variables

```bash
# Default delegation timeout (seconds)
export LLM_DELEGATE_TIMEOUT=120

# Custom tmux session name
export LLM_DELEGATE_SESSION="llm-delegate"
```

### Provider CLI Installation

```bash
# Gemini
pip install google-generativeai
# or: npm install -g @anthropic/gemini-cli

# Codex
npm install -g @openai/codex-cli
# or: pip install openai-codex

# Copilot
gh extension install github/gh-copilot

# Claude (already installed if using this skill)
npm install -g @anthropic/claude-code
```

## Usage Examples

### Large Log Analysis

```bash
# User has 500KB log file
# Claude recognizes it's too large for efficient context use
# Delegates to Gemini:

llm-delegate.sh gemini "Analyze this log file and identify:
1. Error patterns
2. Performance bottlenecks
3. Security concerns

$(cat /path/to/large.log)"
```

### Boilerplate Generation

```bash
# User wants REST API endpoints
# Claude recognizes this is boilerplate
# Delegates to Codex:

llm-delegate.sh codex "Generate TypeScript REST API endpoints for a User model with:
- CRUD operations
- Input validation
- Error handling
- OpenAPI documentation"
```

### Hybrid Approach

1. Delegate boilerplate to Codex
2. Review generated code with Claude
3. Apply Claude's security insights
4. Combine for best result

## Tmux Integration

The delegation script uses tmux for:
- Running CLIs that need TTY
- Capturing streaming output
- Managing multiple concurrent delegations

### Tmux Session Layout

```
llm-delegate (session)
├── Window 0: gemini-cli (if active)
├── Window 1: codex-cli (if active)
└── Window 2: copilot (if active)
```

### Debugging Delegations

```bash
# Attach to delegation session
tmux attach -t llm-delegate

# List active delegations
tmux list-windows -t llm-delegate

# Kill stuck delegation
tmux kill-window -t llm-delegate:0
```

## Cost Optimization

### Estimated Costs (per 1M tokens)

| Provider | Input | Output |
|----------|-------|--------|
| Claude Opus | $15 | $75 |
| Claude Sonnet | $3 | $15 |
| Claude Haiku | $0.25 | $1.25 |
| Gemini Pro | $1.25 | $5 |
| Codex | ~$2 | ~$6 |

### Savings Strategy

- Route large context to Gemini: 10x savings on input
- Route boilerplate to Codex: 5x savings
- Keep reasoning on Claude: best quality where it matters

## Troubleshooting

### Provider Not Found

```bash
# Check which providers are installed
llm-route.sh --list

# Install missing provider
pip install google-generativeai  # Gemini
npm install -g @openai/codex-cli  # Codex
```

### Delegation Timeout

```bash
# Increase timeout for large tasks
llm-delegate.sh -t 300 gemini "analyze entire codebase"

# Or set environment variable
export LLM_DELEGATE_TIMEOUT=300
```

### Output Capture Issues

```bash
# Keep session for manual inspection
llm-delegate.sh -k gemini "task"

# Then attach and check
tmux attach -t llm-delegate
```

## Integration with Other Skills

- **using-tmux**: Provides foundation for CLI delegation
- **batch-operations**: Delegate multiple similar tasks in parallel
- **context-optimizer**: Suggest delegation when context bloated

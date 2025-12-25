---
description: Run claude-flow multi-agent workflows
allowed-tools: Bash(claude-flow:*)
argument-hint: <workflow> "<objective>"
---

# /flow - Claude Flow Orchestration

Run claude-flow workflows for multi-agent task orchestration.

## Arguments
`$ARGUMENTS` - Workflow name (subcommand) and its arguments (e.g., "feature 'Add user auth'" or "quick-review ./src/auth")

## Workflow

Parse `$ARGUMENTS` to extract the workflow name and objective, then execute claude-flow with appropriate options.

### Available Workflows

From `~/.claude-flow/config.yaml`:

| Workflow | Description | Agents |
|----------|-------------|--------|
| `feature` | Full implementation pipeline | orchestrator → batch-editor → code-reviewer → test-generator |
| `security-review` | Deep security analysis | security-reviewer + migration-planner → report |
| `refactor` | Safe refactoring | orchestrator → code-reviewer → batch-editor → verify |
| `quick-review` | Parallel specialist review | security-reviewer + code-reviewer (parallel) |
| `docs` | Documentation generation | technical-researcher → doc-generator |

### Usage Patterns

1. **Run a workflow**
   ```bash
   claude-flow swarm "<workflow>: <objective>"
   ```

2. **Custom multi-agent task**
   ```bash
   claude-flow swarm "<objective>" --agents "agent1,agent2,agent3"
   ```

3. **With worktree isolation**
   ```bash
   claude-flow swarm "<objective>" --worktree
   ```

4. **Hive mind (interactive)**
   ```bash
   claude-flow hive-mind spawn "<objective>"
   ```

### Examples

User: `/flow feature "Add OAuth2 authentication"`
→ Run full feature pipeline for OAuth2 implementation

User: `/flow quick-review`
→ Run parallel security/perf/accessibility review on current directory

User: `/flow security-review ./src/auth`
→ Deep security analysis of auth module

User: `/flow refactor "Extract validation logic into separate module"`
→ Run refactoring pipeline with impact analysis

### Direct Commands

For advanced usage, run claude-flow directly:
```bash
claude-flow --help                    # Full help
claude-flow hive-mind wizard          # Interactive setup
claude-flow swarm "objective"         # Quick swarm
claude-flow start --swarm             # Start with swarm intelligence
```

## When to Bail
- claude-flow not installed or not in PATH
- Invalid workflow name specified
- Objective unclear (ask for clarification)
- Previous workflow still running

## Should NOT Do
- Run workflows without confirming objective
- Override default agents without reason
- Run heavy workflows (feature, refactor) without worktree isolation
- Interrupt running workflows

### Output Format
- Stream progress from claude-flow
- Show agent transitions
- Report final status and any generated artifacts

# Tool & Output Optimization

## LSP Tool (Code Intelligence)
Use for precise navigation instead of grep:
| Operation | Use For |
|-----------|---------|
| `goToDefinition` | Jump to symbol definition |
| `findReferences` | Find all usages of symbol |
| `hover` | Get type info and docs |
| `documentSymbol` | List all symbols in file |
| `incomingCalls` | What calls this function? |
| `outgoingCalls` | What does this function call? |

## Output Compression
**ALWAYS** compress before displaying:
- Git diffs: `compress-diff.sh` | Build logs: `compress-build.sh`
- Test output: `compress-tests.sh` | Stack traces: `compress-stacktrace.sh`

## Scripts (`~/.claude/scripts/`)
| Category | Scripts |
|----------|---------|
| Search | `offload-grep.sh`, `offload-find.sh` |
| Compress | `compress-diff.sh`, `compress-build.sh`, `compress-tests.sh` |
| Analysis | `smart-preview.sh`, `extract-signatures.sh`, `summarize-file.sh` |
| Git | `git-prep.sh`, `git-cleanup.sh` |

## Modern CLI Tools
Auto-suggested by `suggest_tool_optimization.py` hook. Key tools:
- **Search**: `rg` (10x faster), `fd` (4x faster)
- **View**: `bat`, `eza` | **Diff**: `delta`, `difft`
- **Data**: `jq`, `yq`, `gron`, `htmlq`

## Documentation Lookup
**USE** WebSearch for external docs (APIs, language features).
**USE** `claude-code-guide` agent for Claude Code/SDK questions.

## Haiku Routing (80-90% Cost Savings)
**Route to Haiku**: Single-file ops, "What/Where is X?", error explanations, summarization.
**Keep on Opus**: Architecture, complex debugging, security, code review, refactoring.
See `04-skills.md` for full agent list.

## Background & Resume Patterns
- **Long-running agents**: Use `run_in_background=true`
- **Iterative work**: Resume agents with `resume=<agent_id>`

## Token Budget
| Content | Max | Strategy |
|---------|-----|----------|
| Search results | 20 lines | head_limit param |
| File previews | 100 lines | smart-preview.sh |
| Code blocks | 50 lines | Excerpt + reference |
| Diffs/Build/Test | Errors only | compress-*.sh |

## Context Management
- **Clear between tasks**: `/clear` resets context, improves focus
- **File references**: Use `@src/file.ts` to include file + its CLAUDE.md chain
- **Session resume**: `claude --resume <name>` preserves context across sessions
- **Auto-compact**: Triggers at ~80% capacity; manual `/compact` preserves more

## Extended Thinking
- **Toggle**: **Alt+T**
- **Trigger words**: Prefix with "ultrathink:" for complex architecture
- **Use for**: Architectural decisions, challenging bugs, multi-step planning

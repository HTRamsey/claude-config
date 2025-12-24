---
name: efficient-search
description: Use for codebase exploration, finding files, searching patterns. Triggers on "find X", "where is X", exploratory searches. Prioritizes token efficiency through head_limit, progressive refinement, and Task(Explore) delegation.
---

# Efficient Search

**Persona:** Token miser - every search result costs tokens, find exactly what's needed, nothing more.

## Should NOT Attempt

- Run open-ended searches directly (use Task Explore)
- Return unlimited search results
- Search without head_limit on large codebases
- Read entire files when only a section is needed

## Decision Tree

| Question | YES | NO |
|----------|-----|-----|
| Know exact file/function? | `Glob`/`Grep` directly | Continue |
| Exploratory/open-ended? | `Task(Explore)` | Continue |
| Searching code structure? | `smart-ast.sh` | `Grep` with `head_limit` |
| Multiple criteria? | `Task(Explore)` thorough | Single `Grep`/`Glob` |

## Token-Efficient Patterns

```bash
# Limit results
Grep with head_limit: 20, output_mode: files_with_matches

# Offload scripts (97% savings)
~/.claude/scripts/offload-grep.sh 'pattern' ./src 10
~/.claude/scripts/offload-find.sh ./src '*.py' 20

# Structural over regex
~/.claude/scripts/smart-ast.sh 'def $NAME($$$): $$$' ./src python compact

# Parallel tool calls (same message)
Grep(pattern="async def", path="./src/api")
Grep(pattern="async def", path="./src/services")
```

## Progressive Refinement

1. Start narrow (specific file/pattern)
2. Widen only if needed
3. Never start with `**/*` patterns

## Anti-Patterns

- Reading files "just in case"
- Grep without head_limit on large codebases
- Multiple similar searches (use Task agent)
- Reading entire files for one function
- Searching the same pattern multiple times
- Using Grep when you already know the file path

## Examples

### Example 1: Find a Function Definition
**Query:** "Where is handleAuth defined?"
**Approach:** Known target → direct search
```
Grep(pattern="function handleAuth|def handleAuth|handleAuth =", head_limit=5)
```
**Result:** `src/auth/handlers.ts:42`

### Example 2: Understand a System
**Query:** "How does the caching layer work?"
**Approach:** Open-ended exploration → delegate
```
Task(subagent_type=Explore, prompt="Explain the caching architecture")
```
**Result:** Agent explores, returns summary without bloating context

### Example 3: Find All API Endpoints
**Query:** "List all REST endpoints"
**Approach:** Structural search with limits
```
Grep(pattern="@(Get|Post|Put|Delete)|router\.(get|post)", head_limit=30, output_mode=files_with_matches)
```
**Result:** File list, then read specific files as needed

## Output Format

When reporting search results:
```
FOUND: [target description]
Location: [file:line]
Confidence: [high|medium|low]

[3-5 relevant lines of code]

Next: [follow-up action if needed]
```

When search fails:
```
NOT FOUND: [target description]
Searched: [patterns and paths tried]
Near matches: [close results if any]
Suggestion: [alternative approach]
```

## Escalation Triggers

Escalate to `Task(Explore)` when:
- Third search attempt without finding target
- Search matches 50+ files
- Exploratory question ("how does X work?")
- Cross-cutting concern spanning multiple modules

## Failure Behavior

If target not found after 3 attempts:
1. Report what was searched (patterns, paths)
2. List near-matches found
3. Suggest alternative search strategies
4. Ask user for clarification on naming conventions

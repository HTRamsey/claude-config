# Learnings

Accumulated insights from Claude Code sessions. Not auto-loaded - read on-demand.

## Categories

| File | Topics |
|------|--------|
| `skills.md` | Skill design, AgentSkills spec, progressive disclosure |
| `hooks.md` | Hook implementation, dispatchers, async patterns |
| `agents.md` | Subagent design, routing, coordination |
| `debugging.md` | Debugging insights, root cause patterns |
| `workflows.md` | Process improvements, efficiency gains |
| `anti-patterns.md` | What NOT to do, common mistakes |

## Entry Format

```markdown
## [YYYY-MM-DD] Title

**Context:** What was being done
**Learning:** The insight
**Evidence:** How it was discovered
**Application:** How to use this going forward
```

## Usage

```bash
# Read specific category
cat ~/.claude/learnings/skills.md

# Search across all learnings
grep -r "pattern" ~/.claude/learnings/

# Recent entries
head -50 ~/.claude/learnings/*.md
```

## Adding Learnings

After discovering something useful, add an entry to the appropriate file. Keep entries concise - the insight should be actionable.

# Config Design Patterns

Anti-patterns and best practices for ~/.claude configuration.

## Anti-Patterns

| Don't | Why | Instead |
|-------|-----|---------|
| Keep counts of agents/skills/commands | Goes stale, maintenance burden | Let scripts count dynamically |
| Duplicate content across files | Drift, inconsistency | Single source of truth, reference it |
| Hardcode paths in multiple places | Breaks on reorganization | Use variables or reference architecture.md |
| Create agents for single-use tasks | Bloat, never used again | Just do the task inline |
| Over-specialize agents | Too many to remember | Merge related capabilities |
| Generic agents without clear triggers | Never invoked | Specific triggers in description |

## Agent Design

| Do | Don't |
|----|-------|
| Minimal tool set needed | Give all tools "just in case" |
| Clear trigger words in description | Vague descriptions |
| Delegate to specialists | Duplicate expertise |
| Specify output format | Leave format unspecified |
| Include "When NOT to Use" section | Assume scope is obvious |
| Route simple tasks to Haiku | Use Opus for everything |

## Hook Design

| Do | Don't |
|----|-------|
| Use dispatchers for PreToolUse/PostToolUse | Register hooks individually |
| Fail gracefully (hook_utils.py patterns) | Let errors crash |
| Target specific tools only | Watch all tools unnecessarily |
| Keep under 100ms latency | Block on slow operations |
| Log to hook-events.jsonl | Print to stdout |

## File Organization

| Do | Don't |
|----|-------|
| One source of truth per concept | Scatter related info |
| Update architecture.md when adding components | Add files without documentation |
| Use creator skills for new config | Create files manually |
| Delete unused config | Leave dead code "just in case" |

## Documentation

| Do | Don't |
|----|-------|
| Tables over prose | Long paragraphs |
| Examples over explanations | Abstract descriptions |
| Link to authoritative source | Duplicate content |
| Keep reference.md as index only | Put details in reference.md |

## Maintenance

| Do | Don't |
|----|-------|
| Run health-check.sh after changes | Assume changes work |
| Check usage-stats.json before deleting | Delete based on gut feeling |
| Update cross-references after moves | Leave broken references |
| Validate with validate-config.sh | Skip validation |

## Progressive Skill Format

Three-tier loading to minimize token usage (60-80% reduction for skill-heavy workflows).

### Directory Structure

```
skills/<name>/
├── metadata.yml      # Tier 1: ~50 tokens (always scannable)
├── instructions.md   # Tier 2: ~200 tokens (core rules)
├── SKILL.md          # Tier 3: Full content (on demand)
└── resources/        # Tier 3: Examples, templates
    ├── examples/
    └── templates/
```

### Tier Content

| Tier | File | Content | Tokens | When Loaded |
|------|------|---------|--------|-------------|
| 1 | `metadata.yml` | Name, triggers, one-line summary | ~50 | Always (index scanning) |
| 2 | `instructions.md` | Core rules, quick reference | ~200 | On activation |
| 3 | `SKILL.md` + `resources/` | Full docs, examples, templates | Variable | On demand |

### metadata.yml Format

```yaml
name: skill-name
version: 1.0.0

triggers:
  - keyword1
  - keyword2
  - "phrase trigger"

description: |
  One-line description of when to use this skill.

summary: |
  2-3 bullet points of core behavior.

quick_reference:
  - "Rule 1"
  - "Rule 2"
```

### Usage

```bash
# Load tier 1 only (quick scan)
~/.claude/scripts/smart/skill-loader.sh test-driven-development 1

# Load tier 2 (core instructions)
~/.claude/scripts/smart/skill-loader.sh test-driven-development 2

# Load full skill (default)
~/.claude/scripts/smart/skill-loader.sh test-driven-development 3
```

### When to Use Progressive Format

- **High-frequency skills** - Loaded often, benefit from tiering
- **Large skills** - >500 lines benefit most from tiering
- **Reference-heavy skills** - Keep examples in tier 3

### Migration Checklist

1. Create `metadata.yml` with triggers and summary
2. Extract core rules to `instructions.md`
3. Keep full content in `SKILL.md`
4. Move examples to `resources/examples/`
5. Test with `skill-loader.sh` at each tier

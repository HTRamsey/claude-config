---
name: skill-creator
description: Guide for creating effective skills. This skill should be used when users want to create a new skill (or update an existing skill) that extends Claude's capabilities with specialized knowledge, workflows, or tool integrations.
---

# Skill Creator

**Persona:** Curriculum designer creating focused, teachable modules - prioritizes clarity and immediate usability.

Skills are modular packages extending Claude with specialized knowledge, workflows, and tools.

## Skill Structure

```
skill-name/
├── SKILL.md (required) - YAML frontmatter (name, description) + instructions
└── Bundled Resources (optional)
    ├── scripts/     - Executable code for deterministic/repeated tasks
    ├── references/  - Documentation loaded into context as needed
    └── assets/      - Files used in output (templates, icons, fonts)
```

### Resource Guidelines

| Type | When to Include | Example |
|------|-----------------|---------|
| scripts/ | Same code rewritten repeatedly, needs deterministic reliability | `rotate_pdf.py` |
| references/ | Documentation Claude should reference while working | `schema.md`, `api_docs.md` |
| assets/ | Files used in final output, not loaded into context | `logo.png`, `template.pptx` |

**Progressive loading:** Metadata always in context (~100 words) -> SKILL.md when triggered (<5k words) -> Resources as needed

## Should NOT Attempt

- Creating skills that duplicate existing ones (check first)
- Skills that are too broad (split into focused skills)
- Skills with more than 5k words (keep SKILL.md concise)
- Skills that should be commands (user-initiated workflows) or agents (delegated tasks)
- Including large references inline (use references/ directory)

## Failure Behavior

When unable to create a skill:
1. State what's blocking (unclear scope, conflicting requirements)
2. Ask clarifying questions with concrete examples
3. Suggest alternative approaches (command, agent, or simpler skill)

## Escalation Triggers

| Situation | Escalate To |
|-----------|-------------|
| Scope unclear after 2 rounds | User clarification with examples |
| Significant overlap with existing | Extend existing skill instead |
| Better as command/agent | `command-creator` or `agent-creator` skill |
| Resources exceed reasonable size | Split into multiple focused skills |

## Creation Process

### Step 1: Understand with Concrete Examples

Ask: "What functionality should this skill support?", "Can you give usage examples?", "What should trigger this skill?"

Skip only when usage patterns are already clear.

### Step 2: Plan Reusable Contents

For each example, analyze:
1. How to execute from scratch
2. What scripts/references/assets would help when repeating

| Example Query | Reusable Resource |
|---------------|-------------------|
| "Rotate this PDF" | `scripts/rotate_pdf.py` |
| "Build me a todo app" | `assets/hello-world/` template |
| "How many users logged in?" | `references/schema.md` |

### Step 3: Initialize

```bash
~/.claude/skills/skill-creator/scripts/init_skill.py <skill-name> --path <output-directory>
```

Creates: skill directory, SKILL.md template, example `scripts/`, `references/`, `assets/` directories.

### Step 4: Edit the Skill

**Writing style:** Imperative/infinitive form ("To accomplish X, do Y" not "You should do X")

**SKILL.md must answer:**
1. What is the skill's purpose?
2. When should it be used?
3. How should Claude use it? (Reference all bundled resources)

**SKILL.md should include:**
- Persona (brief statement shaping behavior)
- Should NOT Attempt (explicit anti-patterns)
- Failure Behavior (what to do when blocked)
- Escalation (when to recommend alternatives)

Delete unused example directories.

### Step 5: Package

```bash
~/.claude/skills/skill-creator/scripts/package_skill.py <path/to/skill-folder> [output-dir]
```

Validates (frontmatter, structure, description quality) then creates distributable zip.

### Step 6: Iterate

Use skill on real tasks -> notice struggles -> update SKILL.md or resources -> test again

## Template

```markdown
---
name: skill-name
description: One sentence on when to use this skill. Be specific about triggers.
---

# Skill Name

{One paragraph explaining what this skill teaches Claude to do.}

## Persona

{1-2 sentences establishing expertise/approach that shapes behavior.}

## When to Use

- {Trigger condition 1}
- {Trigger condition 2}

## Process

1. **{Step name}:** {What to do}
2. **{Step name}:** {What to do}
3. **{Step name}:** {What to do}

## Examples

### Example 1: {Scenario}
{Show input and expected output/behavior}

## Should NOT Attempt

- {Anti-pattern 1}
- {Anti-pattern 2}

## Escalation

When to recommend a different approach or ask for guidance.

## Resources

- `scripts/X.py`: {What it does}
- `references/Y.md`: {What it contains}
```

## Skill vs Command vs Agent

| Aspect | Skill | Command | Agent |
|--------|-------|---------|-------|
| Trigger | Auto or `/skill-name` | `/command-name` only | `Task(subagent_type)` |
| Purpose | Procedural knowledge | User workflow | Delegated task |
| Scope | How to think about X | Steps to do X | Execute X separately |
| Example | `systematic-debugging` | `/commit` | `code-reviewer` |

Choose skill when: Claude needs to learn a methodology or approach.
Choose command when: User wants a repeatable workflow.
Choose agent when: Task should be delegated to a subagent.

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Skill too broad | Split into focused skills |
| No concrete examples | Add 2-3 real usage scenarios |
| Missing trigger conditions | Add "When to Use" section |
| Too much inline content | Move to references/ |
| No anti-patterns | Add "Should NOT Attempt" |
| No failure guidance | Add what to do when blocked |

## Related Skills

- **hook-creator**: Create hooks skills reference
- **agent-creator**: Create agents skills invoke
- **command-creator**: Create commands for skills

## When Blocked

If unable to create a working skill:
- Request more concrete examples of usage
- Check if existing skills already cover the use case
- Consider if command or agent is more appropriate
- Start with minimal skill and iterate based on real usage

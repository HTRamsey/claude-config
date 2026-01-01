---
name: skill-creator
description: Guide for creating effective skills. This skill should be used when users want to create a new skill (or update an existing skill) that extends Claude's capabilities with specialized knowledge, workflows, or tool integrations.
---

# Skill Creator

**Persona:** Curriculum designer creating focused, teachable modules - prioritizes clarity and immediate usability.

Skills are modular packages extending Claude with specialized knowledge, workflows, and tools.

## Skill Structure

Skills use a **3-tier progressive format** for optimal context usage:

```
skill-name/
├── metadata.yml (Tier 1)      - ~50 tokens, always loaded
├── instructions.md (Tier 2)   - ~200 tokens, core workflow
├── SKILL.md (Tier 3)          - Full content, loaded on-demand
└── resources/ (Tier 3)        - Advanced materials
    ├── examples/              - Usage examples
    ├── templates/             - Reusable templates
    ├── scripts/               - Executable code
    └── references/            - Detailed documentation
```

### 3-Tier Loading Strategy

| Tier | File | Size | Always Loaded? | Contains |
|------|------|------|----------------|----------|
| **1** | `metadata.yml` | ~50 tokens | Yes | Name, triggers, 1-2 sentence description, quick reference |
| **2** | `instructions.md` | ~200 tokens | When triggered | Core workflow, mandatory checks, anti-patterns, escalation |
| **3** | `SKILL.md` | <5k words | On-demand | Full details, advanced topics, examples, edge cases |
| **3** | `resources/` | Variable | As needed | Templates, scripts, references, examples |

### Tier 1: metadata.yml (~50 tokens)

The skill's "business card" - always in context, enables auto-triggering.

```yaml
name: skill-name
version: 1.0.0

triggers:
  - keyword or phrase
  - another trigger
  - specific context

description: |
  One sentence what it does. One sentence when to use it.

summary: |
  2-3 line workflow summary
  Key principle or constraint

quick_reference:
  - "Step 1 in brief"
  - "Step 2 in brief"
  - "Critical rule"
```

**Token budget:** ~50 tokens. Every word counts.

### Tier 2: instructions.md (~200 tokens)

Core workflow loaded when skill is triggered. Must be self-contained for simple cases.

**Must include:**
- Core workflow (numbered steps)
- Mandatory checks (verification gates)
- Should NOT do (anti-patterns)
- Escalate when (complexity triggers)

**Optional:**
- Quick commands table
- Common patterns
- Reference to Tier 3 for advanced topics

**Token budget:** ~200 tokens. Focus on the 80% case.

### Tier 3: SKILL.md & resources/ (on-demand)

Full detailed content loaded only when needed for complex scenarios.

**SKILL.md includes:**
- Detailed explanations
- Edge cases and advanced topics
- Comprehensive examples
- Troubleshooting guides
- Philosophy and principles

**resources/ includes:**
| Type | When to Include | Example |
|------|-----------------|---------|
| examples/ | Concrete usage scenarios | `api-integration/`, `async-test/` |
| templates/ | Reusable file templates | `test-template.py`, `config.json` |
| scripts/ | Executable code for repeated tasks | `rotate_pdf.py`, `analyze.sh` |
| references/ | Documentation to reference while working | `schema.md`, `api_docs.md` |

**Progressive loading:** metadata.yml (always) -> instructions.md (when triggered) -> SKILL.md (complex cases) -> resources/ (as needed)

## Core Principles

### Conciseness is Key

The context window is a public good. Claude is already very smart - only add context Claude doesn't already have.

Challenge each piece: "Does Claude really need this?" Prefer concise examples over verbose explanations.

### Degrees of Freedom

Match specificity to task fragility:

| Freedom | Format | Use When |
|---------|--------|----------|
| High | Text instructions | Multiple approaches valid, context-dependent |
| Medium | Pseudocode/parameterized scripts | Preferred pattern exists, some variation OK |
| Low | Specific scripts, few params | Operations fragile, consistency critical |

### Triggers Enable Auto-Activation

The `triggers` and `description` fields in **metadata.yml** are the **primary mechanism** for skill activation.

**triggers:** Keywords/phrases that should activate this skill
**description:** 1-2 sentences: what it does + when to use it
**summary:** The core workflow/constraint in 2-3 lines

These fields are ALWAYS loaded (Tier 1). They enable Claude to auto-trigger the skill when relevant.

Do NOT put "When to Use" in instructions.md or SKILL.md - those load AFTER triggering.

## Should NOT Attempt

- Creating skills that duplicate existing ones (check first)
- Skills that are too broad (split into focused skills)
- Skills with more than 5k words in SKILL.md (move to resources/)
- Skills that should be commands (user-initiated workflows) or agents (delegated tasks)
- Including large references inline (use resources/references/)
- Putting triggers/description in SKILL.md (belongs in metadata.yml)
- Creating single-file skills (use 3-tier format)

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
| "Rotate this PDF" | `resources/scripts/rotate_pdf.py` |
| "Build me a todo app" | `resources/templates/hello-world/` |
| "How many users logged in?" | `resources/references/schema.md` |

### Step 3: Initialize

```bash
~/.claude/skills/skill-creator/scripts/init_skill.py <skill-name> --path <output-directory>
```

Creates: skill directory with 3-tier structure (metadata.yml, instructions.md, SKILL.md, resources/)

### Step 4: Edit the Skill

**Writing style:** Imperative/infinitive form ("To accomplish X, do Y" not "You should do X")

**Edit in order:**

1. **metadata.yml (~50 tokens):**
   - Add specific trigger keywords
   - Write clear 1-2 sentence description
   - Distill summary to 2-3 lines
   - Create quick reference bullets

2. **instructions.md (~200 tokens):**
   - Define core workflow (numbered steps)
   - Add mandatory checks/verification gates
   - List "Should NOT Do" anti-patterns
   - List "Escalate When" complexity triggers
   - Add quick commands if applicable

3. **SKILL.md (detailed):**
   - Remove TODO placeholders
   - Keep/expand persona statement
   - Provide detailed process explanations
   - Add comprehensive examples
   - Cover advanced topics and edge cases
   - Reference resources/ as needed

4. **resources/:**
   - Customize or delete example files
   - Add concrete examples in examples/
   - Add reusable templates in templates/
   - Add scripts/references only if needed

### Step 5: Package

```bash
~/.claude/skills/skill-creator/scripts/package_skill.py <path/to/skill-folder> [output-dir]
```

Validates (frontmatter, structure, description quality) then creates distributable zip.

### Step 6: Iterate

Use skill on real tasks -> notice struggles -> update SKILL.md or resources -> test again

## Migrating Existing Skills

For skills with old single-file format (YAML frontmatter + content in SKILL.md):

1. **Extract metadata.yml:**
   - Copy `name` from frontmatter
   - Add `version: 1.0.0`
   - Create `triggers` list from description/context
   - Write 1-2 sentence `description`
   - Distill `summary` to 2-3 lines
   - Create `quick_reference` bullets (~3-5 items)

2. **Create instructions.md:**
   - Extract core workflow/process (numbered steps)
   - Add mandatory checks/verification gates
   - List anti-patterns ("Should NOT Do")
   - List escalation triggers ("Escalate When")
   - Keep under 200 tokens

3. **Update SKILL.md:**
   - Remove frontmatter (now in metadata.yml)
   - Remove core workflow (now in instructions.md)
   - Keep detailed explanations, examples, edge cases
   - Expand on advanced topics
   - Reference instructions.md for basic workflow

4. **Organize resources:**
   - Move existing `scripts/` to `resources/scripts/` (optional)
   - Move existing `references/` to `resources/references/` (optional)
   - Add `resources/examples/` for concrete scenarios
   - Add `resources/templates/` for reusable files

**Token targets:** metadata.yml ~50, instructions.md ~200, SKILL.md <5k words

## Template

### metadata.yml (Tier 1, ~50 tokens)

```yaml
name: skill-name
version: 1.0.0

triggers:
  - primary keyword
  - context phrase
  - specific scenario

description: |
  One sentence what it does. One sentence when to use it.

summary: |
  Core workflow in 2-3 lines
  Key principle or constraint

quick_reference:
  - "Step 1 brief"
  - "Step 2 brief"
  - "Critical rule"
```

### instructions.md (Tier 2, ~200 tokens)

```markdown
# {Skill Name} Instructions (Tier 2)

{One-line constraint or principle if critical.}

## Cycle/Process

1. **{Step}:** {What to do}
2. **{Step}:** {What to do}
3. **{Step}:** {What to do}

## Mandatory Checks

Before X:
- Verify Y
- Confirm Z

## Should NOT Do

- {Anti-pattern 1}
- {Anti-pattern 2}

## Escalate When

- {Complexity trigger 1}
- {Complexity trigger 2}

## Quick Commands

\```bash
# Common operation
command --flag

# Another operation
command2
\```

For {advanced topic}, see SKILL.md.
```

### SKILL.md (Tier 3, detailed)

```markdown
---
name: skill-name
description: What this skill does AND when to use it.
---

# Skill Name

{One paragraph: what this skill teaches Claude to do.}

## Persona

{1-2 sentences: expertise/approach shaping behavior.}

## Detailed Process

1. **{Step}:** {Detailed explanation}
2. **{Step}:** {Detailed explanation}

## Examples

### {Scenario}
{Input and expected behavior - detailed}

## Advanced Topics

### {Topic}
{Explanation}

## Should NOT Attempt

- {Anti-pattern 1 with explanation}
- {Anti-pattern 2 with explanation}

## Escalation

{When to recommend alternatives or ask for guidance.}

## Resources

- `resources/examples/X/`: {Purpose}
- `resources/templates/Y`: {Usage}
- `resources/scripts/Z.py`: {What it does}
```

**Note:** Triggers and "When to Use" belong in metadata.yml (Tier 1), not in instructions.md or SKILL.md.

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
| Missing triggers in metadata.yml | Add specific trigger keywords |
| Too much inline content | Move to resources/ |
| No anti-patterns | Add "Should NOT Do" in instructions.md |
| No failure guidance | Add "Escalate When" section |
| Triggers in SKILL.md not metadata.yml | Move to metadata.yml Tier 1 |
| Core workflow only in SKILL.md | Put in instructions.md Tier 2 |
| metadata.yml exceeds 50 tokens | Trim to essential info only |
| instructions.md exceeds 200 tokens | Move details to SKILL.md |

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

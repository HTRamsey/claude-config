# Skill Learnings

## [2025-12-25] Description Field is the Primary Trigger

**Context:** Reviewing AgentSkills spec and Anthropic's skill-creator
**Learning:** The `description` field in YAML frontmatter is the ONLY thing Claude sees before deciding to activate a skill. "When to Use" sections in the body are useless - the body loads AFTER triggering.
**Evidence:** AgentSkills spec explicitly states description should include "what the skill does and when to use it"
**Application:** Always put trigger conditions in description. Never have "When to Use" as a body section.

## [2025-12-25] Progressive Disclosure - Three Levels

**Context:** Analyzing Anthropic's PDF skill structure
**Learning:** Skills load in three stages: (1) Metadata ~100 tokens always loaded, (2) SKILL.md body <5K tokens when triggered, (3) references/scripts on-demand unlimited. Design accordingly.
**Evidence:** AgentSkills spec and Anthropic skill-creator both emphasize this pattern
**Application:** Keep SKILL.md under 500 lines. Move large sections to `references/`. Move deterministic code to `scripts/`.

## [2025-12-25] Conciseness is Key

**Context:** Anthropic skill-creator principles
**Learning:** "The context window is a public good. Claude is already very smart - only add context Claude doesn't already have." Challenge each piece: does it justify its token cost?
**Evidence:** Anthropic's official guidance in skill-creator SKILL.md
**Application:** Prefer concise examples over verbose explanations. Delete anything Claude already knows.

## [2025-12-25] YAML Frontmatter - Quote Values with Colons

**Context:** skills-ref validation failing on compatibility fields
**Learning:** YAML values containing colons (`:`) must be quoted, otherwise YAML parser treats them as nested mappings.
**Evidence:** `compatibility: C++: Valgrind` fails, `compatibility: "C++ requires Valgrind"` works
**Application:** Always quote string values in frontmatter if they contain colons, or rephrase to avoid colons.

## [2025-12-25] Skill vs Command vs Agent

**Context:** Skill-creator guidance on when to use each
**Learning:**
- **Skill**: Procedural knowledge, methodology (how to think about X)
- **Command**: User-initiated workflow (steps to do X)
- **Agent**: Delegated task execution (execute X separately)
**Evidence:** Anthropic skill-creator comparison table
**Application:** Choose skill when Claude needs to learn an approach. Choose command for repeatable user workflows. Choose agent for isolated task delegation.

## [2025-12-25] allowed-tools Field (Experimental)

**Context:** AgentSkills spec optional fields
**Learning:** The `allowed-tools` frontmatter field can pre-approve specific tools (e.g., `Bash(git:*) Read`). Experimental - support varies by implementation.
**Evidence:** AgentSkills specification
**Application:** Use sparingly for skills that require specific tool access patterns.

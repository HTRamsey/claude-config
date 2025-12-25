# External Resources

Reference materials from external sources. These are not auto-loaded - use for reference when needed.

## Structure

```
resources/
├── anthropic/
│   └── skill-creator/       # Official Anthropic skill-creator
│       ├── SKILL.md          # The definitive skill creation guide
│       ├── references/
│       │   ├── workflows.md       # Workflow patterns
│       │   └── output-patterns.md # Output formatting patterns
│       └── scripts/
│           ├── init_skill.py      # Official init script
│           ├── package_skill.py   # Official packaging script
│           └── quick_validate.py  # Validation logic
│
└── agentskills/
    ├── README.md             # AgentSkills overview
    ├── skills-ref/           # Reference SDK (installed to venv)
    │   ├── src/skills_ref/   # SDK source code
    │   └── tests/            # SDK tests
    ├── docs/                 # AgentSkills.io documentation
    │   └── specification.mdx # Full specification
    └── claude-config-example/
        ├── settings.json     # Example settings
        └── hooks/
            └── session-start.sh  # Async hook example
```

## Usage

### Reference Anthropic's skill-creator
```bash
cat ~/.claude/resources/anthropic/skill-creator/SKILL.md
cat ~/.claude/resources/anthropic/skill-creator/references/workflows.md
```

### Check AgentSkills specification
```bash
cat ~/.claude/resources/agentskills/docs/specification.mdx
```

### Use skills-ref CLI (installed to venv)
```bash
~/.claude/scripts/diagnostics/skills-ref.sh validate <skill-path>
~/.claude/scripts/diagnostics/skills-ref.sh read <skill-path>
~/.claude/scripts/diagnostics/skills-ref.sh prompt <skill-path>
```

## Sources

| Resource | Source | Purpose |
|----------|--------|---------|
| skill-creator | github.com/anthropics/skills | Official skill creation guide |
| skills-ref SDK | github.com/agentskills/agentskills | Skill validation & tooling |
| specification | agentskills.io | Open format specification |

## See Also

- `skills/pdf/` - Example well-structured skill (from anthropics/skills)
- `skills/skill-creator/` - Our local skill-creator (based on Anthropic's)

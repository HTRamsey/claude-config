#!/usr/bin/env python3
"""
Skill Initializer - Creates a new skill from template

Usage:
    init_skill.py <skill-name> --path <path>

Examples:
    init_skill.py my-new-skill --path skills/public
    init_skill.py my-api-helper --path skills/private
    init_skill.py custom-skill --path /custom/location
"""

import sys
from pathlib import Path


METADATA_TEMPLATE = """# Tier 1: Metadata (always loaded, ~50 tokens)
name: {skill_name}
version: 1.0.0

triggers:
  - [TODO: primary keyword]
  - [TODO: context phrase]
  - [TODO: specific scenario]

description: |
  [TODO: One sentence what it does. One sentence when to use it.]

summary: |
  [TODO: Core workflow in 2-3 lines]
  [TODO: Key principle or constraint]

quick_reference:
  - "[TODO: Step 1 brief]"
  - "[TODO: Step 2 brief]"
  - "[TODO: Critical rule]"
"""

INSTRUCTIONS_TEMPLATE = """# {skill_title} Instructions (Tier 2)

[TODO: One-line constraint or principle if critical.]

## Cycle/Process

1. **[Step 1]:** [What to do]
2. **[Step 2]:** [What to do]
3. **[Step 3]:** [What to do]

## Mandatory Checks

Before X:
- [TODO: Verify Y]
- [TODO: Confirm Z]

## Should NOT Do

- [TODO: Anti-pattern 1]
- [TODO: Anti-pattern 2]

## Escalate When

- [TODO: Complexity trigger 1]
- [TODO: Complexity trigger 2]

## Quick Commands

```bash
# [TODO: Common operation]
command --flag

# [TODO: Another operation]
command2
```

For [advanced topic], see SKILL.md.
"""

SKILL_TEMPLATE = """---
name: {skill_name}
description: [TODO: What this skill does AND when to use it. Keep consistent with metadata.yml.]
---

# {skill_title}

[TODO: One paragraph explaining what this skill teaches Claude to do.]

## Persona

[TODO: 1-2 sentences establishing expertise/approach that shapes behavior.]

## Detailed Process

1. **[Step 1]:** [Detailed explanation with context]
2. **[Step 2]:** [Detailed explanation with context]
3. **[Step 3]:** [Detailed explanation with context]

## Examples

### [Scenario 1]
[Input and expected behavior - detailed example]

### [Scenario 2]
[Another example showing edge case or variation]

## Advanced Topics

### [Topic 1]
[Explanation of complex scenario or edge case]

### [Topic 2]
[Another advanced consideration]

## Should NOT Attempt

- [Anti-pattern 1 with detailed explanation]
- [Anti-pattern 2 with detailed explanation]

## Escalation

[When to recommend alternatives or ask for guidance. Include specific thresholds.]

## Resources

- `resources/examples/[example-name]/`: [Purpose and when to reference]
- `resources/templates/[template-name]`: [Usage and customization notes]

---

**Note:** Core workflow is in instructions.md. This file provides depth for complex cases.
"""

EXAMPLE_TEMPLATE = """# Example: [Scenario Name]

This is a template showing how to use {skill_name} for a specific scenario.

## Context

[Describe when this example applies]

## Input

[What the user provides or what situation triggers this]

## Process

1. [Step with specific details]
2. [Step with specific details]
3. [Step with specific details]

## Output

[What the result looks like]

## Notes

- [Important consideration 1]
- [Important consideration 2]
"""

TEMPLATE_FILE = """# Template for {skill_title}

[TODO: Replace this with a reusable template file that users can copy/customize]

Examples:
- Code template (test file structure, configuration file)
- Workflow template (checklist, process document)
- Data template (JSON schema, YAML config)

Delete if not needed.
"""


def title_case_skill_name(skill_name):
    """Convert hyphenated skill name to Title Case for display."""
    return ' '.join(word.capitalize() for word in skill_name.split('-'))


def init_skill(skill_name, path):
    """
    Initialize a new skill directory with 3-tier progressive format.

    Args:
        skill_name: Name of the skill
        path: Path where the skill directory should be created

    Returns:
        Path to created skill directory, or None if error
    """
    skill_dir = Path(path).resolve() / skill_name

    if skill_dir.exists():
        print(f"Error: Skill directory already exists: {skill_dir}")
        return None

    try:
        skill_dir.mkdir(parents=True, exist_ok=False)
        print(f"Created skill directory: {skill_dir}")
    except Exception as e:
        print(f"Error creating directory: {e}")
        return None

    skill_title = title_case_skill_name(skill_name)

    # Create Tier 1: metadata.yml
    try:
        metadata_content = METADATA_TEMPLATE.format(skill_name=skill_name)
        metadata_path = skill_dir / 'metadata.yml'
        metadata_path.write_text(metadata_content)
        print("Created metadata.yml (Tier 1)")
    except Exception as e:
        print(f"Error creating metadata.yml: {e}")
        return None

    # Create Tier 2: instructions.md
    try:
        instructions_content = INSTRUCTIONS_TEMPLATE.format(
            skill_name=skill_name,
            skill_title=skill_title
        )
        instructions_path = skill_dir / 'instructions.md'
        instructions_path.write_text(instructions_content)
        print("Created instructions.md (Tier 2)")
    except Exception as e:
        print(f"Error creating instructions.md: {e}")
        return None

    # Create Tier 3: SKILL.md
    try:
        skill_content = SKILL_TEMPLATE.format(
            skill_name=skill_name,
            skill_title=skill_title
        )
        skill_md_path = skill_dir / 'SKILL.md'
        skill_md_path.write_text(skill_content)
        print("Created SKILL.md (Tier 3)")
    except Exception as e:
        print(f"Error creating SKILL.md: {e}")
        return None

    # Create resources/ directory structure
    try:
        resources_dir = skill_dir / 'resources'
        resources_dir.mkdir(exist_ok=True)

        # examples/
        examples_dir = resources_dir / 'examples'
        examples_dir.mkdir(exist_ok=True)
        example_file = examples_dir / 'example-scenario.md'
        example_file.write_text(EXAMPLE_TEMPLATE.format(
            skill_name=skill_name,
            skill_title=skill_title
        ))
        print("Created resources/examples/example-scenario.md")

        # templates/
        templates_dir = resources_dir / 'templates'
        templates_dir.mkdir(exist_ok=True)
        template_file = templates_dir / 'template.md'
        template_file.write_text(TEMPLATE_FILE.format(
            skill_name=skill_name,
            skill_title=skill_title
        ))
        print("Created resources/templates/template.md")

    except Exception as e:
        print(f"Error creating resource directories: {e}")
        return None

    print(f"\nSkill '{skill_name}' initialized at {skill_dir}")
    print("\nNext steps:")
    print("1. Edit metadata.yml - add triggers, description, summary (~50 tokens)")
    print("2. Edit instructions.md - core workflow, checks, anti-patterns (~200 tokens)")
    print("3. Edit SKILL.md - detailed content, examples, advanced topics")
    print("4. Customize or delete example files in resources/")
    print("5. Run package_skill.py to validate and package when ready")

    return skill_dir


def main():
    if len(sys.argv) < 4 or sys.argv[2] != '--path':
        print("Usage: init_skill.py <skill-name> --path <path>")
        print("\nSkill name requirements:")
        print("  - Hyphen-case (e.g., 'data-analyzer')")
        print("  - Lowercase letters, digits, hyphens only")
        print("  - Max 40 characters")
        print("\nExamples:")
        print("  init_skill.py my-new-skill --path ~/.claude/skills")
        print("  init_skill.py pdf-helper --path ./skills")
        sys.exit(1)

    skill_name = sys.argv[1]
    path = sys.argv[3]

    print(f"Initializing skill: {skill_name}")
    print(f"Location: {path}\n")

    result = init_skill(skill_name, path)
    sys.exit(0 if result else 1)


if __name__ == "__main__":
    main()

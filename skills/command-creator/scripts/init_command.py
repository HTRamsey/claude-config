#!/usr/bin/env python3
"""
Command Initializer - Creates a new slash command from template

Usage:
    init_command.py <command-name> --description "<description>" [--global]

Examples:
    init_command.py my-command --description "Do something useful"
    init_command.py deploy --description "Deploy to production" --global
"""

import sys
from pathlib import Path

COMMAND_TEMPLATE = '''# /{command_name}

{description}

## Workflow

1. **[TODO: Step name]:**
   ```bash
   [example command]
   ```

2. **[TODO: Step name]:**
   - [Action item]
   - [Action item]

3. **[TODO: Step name]:**
   ```bash
   [example command]
   ```

## Examples

[TODO: Show 2-3 example outputs]

## Should NOT Do
- [TODO: Anti-pattern 1]
- [TODO: Anti-pattern 2]

## When to Bail
[TODO: When the command should stop and ask for guidance]
- Tests fail before starting
- Uncommitted changes exist
- Can't identify scope

## Escalation
If this command can't complete:
- Recommend alternative commands or agents
- Ask user for clarification

## Rules
- [TODO: Constraint 1]
- [TODO: Constraint 2]
'''


def init_command(command_name, description, is_global):
    """
    Initialize a new command markdown file.

    Args:
        command_name: Name of the command (kebab-case, without leading /)
        description: One-line description of the command
        is_global: If True, create in ~/.claude/commands/, else .claude/commands/

    Returns:
        Path to created command file, or None if error
    """
    if is_global:
        commands_dir = Path.home() / '.claude' / 'commands'
    else:
        commands_dir = Path.cwd() / '.claude' / 'commands'

    # Ensure commands directory exists
    if not commands_dir.exists():
        try:
            commands_dir.mkdir(parents=True, exist_ok=True)
            print(f"✅ Created commands directory: {commands_dir}")
        except Exception as e:
            print(f"❌ Error creating commands directory: {e}")
            return None

    # Remove leading slash if present
    command_name = command_name.lstrip('/')

    command_file = commands_dir / f"{command_name}.md"

    # Check if file already exists
    if command_file.exists():
        print(f"❌ Error: Command already exists: {command_file}")
        return None

    # Create command content
    content = COMMAND_TEMPLATE.format(
        command_name=command_name,
        description=description
    )

    try:
        command_file.write_text(content)
        print(f"✅ Created command: {command_file}")
    except Exception as e:
        print(f"❌ Error creating command: {e}")
        return None

    print(f"\n✅ Command '/{command_name}' initialized successfully")
    print("\nNext steps:")
    print("1. Edit the command file to complete the TODO sections")
    print("2. Define workflow steps with examples")
    print("3. Add anti-patterns and escalation triggers")
    print(f"\nInvoke with: /{command_name}")

    return command_file


def main():
    args = sys.argv[1:]

    if len(args) < 3 or '--description' not in args:
        print("Usage: init_command.py <command-name> --description \"<description>\" [--global]")
        print("\nArguments:")
        print("  command-name  : Kebab-case identifier (e.g., 'my-command')")
        print("  --description : One-line description (quoted)")
        print("  --global      : Create in ~/.claude/commands/ (default: .claude/commands/)")
        print("\nExamples:")
        print("  init_command.py deploy --description \"Deploy to production\" --global")
        print("  init_command.py test-e2e --description \"Run end-to-end tests\"")
        sys.exit(1)

    command_name = args[0]

    # Parse --description
    try:
        desc_idx = args.index('--description')
        description = args[desc_idx + 1]
    except (ValueError, IndexError):
        print("❌ Error: --description is required")
        sys.exit(1)

    # Parse --global flag
    is_global = '--global' in args

    location = "global (~/.claude/commands/)" if is_global else "project (.claude/commands/)"
    print(f"🚀 Initializing command: /{command_name}")
    print(f"   Location: {location}")
    print()

    result = init_command(command_name, description, is_global)

    if result:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()

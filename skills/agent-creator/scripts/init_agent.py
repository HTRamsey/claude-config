#!/usr/bin/env python3
"""
Agent Initializer - Creates a new agent from template

Usage:
    init_agent.py <agent-name> --model <model> --description "<description>" [--tools "<tools>"]

Examples:
    init_agent.py my-agent --model haiku --description "Quick lookup for X"
    init_agent.py security-checker --model opus --description "Security review" --tools "Read,Grep,Glob"
"""

import sys
from pathlib import Path

AGENT_TEMPLATE = '''---
name: {agent_name}
description: "{description}"
tools: {tools}
model: {model}
---

# Backstory
[TODO: 1-2 sentences establishing persona that shapes behavior]

## Your Role
[TODO: 2-3 sentences on what this agent does]

## Process
1. [TODO: Step 1]
2. [TODO: Step 2]
3. [TODO: Step 3]

## Response Format
[TODO: How to structure output - tables, markdown, code blocks]

## Should NOT Attempt
- [TODO: Anti-pattern 1]
- [TODO: Anti-pattern 2]

## Escalation
[TODO: When to recommend escalating to a more capable agent or human]

## Rules
- [TODO: Constraint 1]
- [TODO: Constraint 2]
'''


def init_agent(agent_name, model, description, tools):
    """
    Initialize a new agent markdown file.

    Args:
        agent_name: Name of the agent (kebab-case)
        model: Model to use (haiku, sonnet, opus)
        description: When to use this agent
        tools: Comma-separated list of tools

    Returns:
        Path to created agent file, or None if error
    """
    agents_dir = Path.home() / '.claude' / 'agents'

    # Ensure agents directory exists
    if not agents_dir.exists():
        print(f"❌ Error: Agents directory does not exist: {agents_dir}")
        return None

    agent_file = agents_dir / f"{agent_name}.md"

    # Check if file already exists
    if agent_file.exists():
        print(f"❌ Error: Agent already exists: {agent_file}")
        return None

    # Validate model
    valid_models = ['haiku', 'sonnet', 'opus']
    if model not in valid_models:
        print(f"❌ Error: Invalid model '{model}'. Must be one of: {', '.join(valid_models)}")
        return None

    # Create agent content
    content = AGENT_TEMPLATE.format(
        agent_name=agent_name,
        description=description,
        tools=tools,
        model=model
    )

    try:
        agent_file.write_text(content)
        print(f"✅ Created agent: {agent_file}")
    except Exception as e:
        print(f"❌ Error creating agent: {e}")
        return None

    print(f"\n✅ Agent '{agent_name}' initialized successfully")
    print("\nNext steps:")
    print("1. Edit the agent file to complete the TODO sections")
    print("2. Add backstory, process, response format")
    print("3. Define anti-patterns and escalation triggers")

    return agent_file


def main():
    # Parse arguments
    args = sys.argv[1:]

    if len(args) < 5 or '--model' not in args or '--description' not in args:
        print("Usage: init_agent.py <agent-name> --model <model> --description \"<description>\" [--tools \"<tools>\"]")
        print("\nArguments:")
        print("  agent-name   : Kebab-case identifier (e.g., 'my-agent')")
        print("  --model      : haiku, sonnet, or opus")
        print("  --description: When to use this agent (quoted)")
        print("  --tools      : Comma-separated tools (default: Read,Grep,Glob)")
        print("\nExamples:")
        print("  init_agent.py quick-lookup --model haiku --description \"Single fact retrieval\"")
        print("  init_agent.py security-reviewer --model opus --description \"Security review\" --tools \"Read,Grep,Glob,Bash\"")
        sys.exit(1)

    agent_name = args[0]

    # Parse --model
    try:
        model_idx = args.index('--model')
        model = args[model_idx + 1]
    except (ValueError, IndexError):
        print("❌ Error: --model is required")
        sys.exit(1)

    # Parse --description
    try:
        desc_idx = args.index('--description')
        description = args[desc_idx + 1]
    except (ValueError, IndexError):
        print("❌ Error: --description is required")
        sys.exit(1)

    # Parse --tools (optional)
    tools = "Read, Grep, Glob"
    if '--tools' in args:
        try:
            tools_idx = args.index('--tools')
            tools = args[tools_idx + 1]
        except IndexError:
            pass

    print(f"🚀 Initializing agent: {agent_name}")
    print(f"   Model: {model}")
    print(f"   Tools: {tools}")
    print()

    result = init_agent(agent_name, model, description, tools)

    if result:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()

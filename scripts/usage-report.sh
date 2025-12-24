#!/usr/bin/env bash
# Agent/Skill/Command usage report
# Usage: usage-report.sh [--json|--summary]
#
# Options:
#   --json     Output raw JSON
#   --summary  Show summary only (default: detailed report)

set -euo pipefail

USAGE_FILE="$HOME/.claude/data/usage-stats.json"
FORMAT="${1:-}"

if [[ ! -f "$USAGE_FILE" ]]; then
    echo "No usage data found at $USAGE_FILE"
    echo "Usage tracking starts after first agent/skill/command use."
    exit 0
fi

if [[ "$FORMAT" == "--json" ]]; then
    cat "$USAGE_FILE"
    exit 0
fi

echo "╔════════════════════════════════════════════════════════════════════╗"
echo "║                    Claude Code Usage Report                        ║"
echo "╚════════════════════════════════════════════════════════════════════╝"
echo ""

# Parse and display with Python for reliable JSON handling
python3 << 'PYTHON'
import json
from datetime import datetime
from pathlib import Path

usage_file = Path.home() / ".claude" / "data" / "usage-stats.json"
if not usage_file.exists():
    exit(0)

with open(usage_file) as f:
    data = json.load(f)

# Agents section
agents = data.get("agents", {})
if agents:
    print("## Agents")
    print(f"{'Name':<30} {'Uses':>6} {'Last Used':<12}")
    print("-" * 52)
    sorted_agents = sorted(agents.items(), key=lambda x: x[1].get("count", 0), reverse=True)
    for name, info in sorted_agents:
        count = info.get("count", 0)
        last = info.get("last_used", "")[:10]
        print(f"{name:<30} {count:>6} {last:<12}")
    print("")

# Skills section
skills = data.get("skills", {})
if skills:
    print("## Skills")
    print(f"{'Name':<30} {'Uses':>6} {'Last Used':<12}")
    print("-" * 52)
    sorted_skills = sorted(skills.items(), key=lambda x: x[1].get("count", 0), reverse=True)
    for name, info in sorted_skills:
        count = info.get("count", 0)
        last = info.get("last_used", "")[:10]
        print(f"{name:<30} {count:>6} {last:<12}")
    print("")

# Commands section
commands = data.get("commands", {})
if commands:
    print("## Commands")
    print(f"{'Name':<30} {'Uses':>6} {'Last Used':<12}")
    print("-" * 52)
    sorted_commands = sorted(commands.items(), key=lambda x: x[1].get("count", 0), reverse=True)
    for name, info in sorted_commands:
        count = info.get("count", 0)
        last = info.get("last_used", "")[:10]
        print(f"{name:<30} {count:>6} {last:<12}")
    print("")

# Summary
print("## Summary")
daily = data.get("daily", {})
total_agents = sum(d.get("agents", 0) for d in daily.values())
total_skills = sum(d.get("skills", 0) for d in daily.values())
total_commands = sum(d.get("commands", 0) for d in daily.values())
print(f"Total agent invocations:   {total_agents}")
print(f"Total skill invocations:   {total_skills}")
print(f"Total command invocations: {total_commands}")
print(f"Tracking since: {data.get('first_seen', 'unknown')[:10]}")

# Unused features
all_agents_dir = Path.home() / ".claude" / "agents"
all_skills_dir = Path.home() / ".claude" / "skills"
all_commands_dir = Path.home() / ".claude" / "commands"

if all_agents_dir.exists():
    # Exclude archive directory
    all_agents = {p.stem for p in all_agents_dir.glob("*.md") if p.parent.name != "archive"}
    used_agents = set(agents.keys())
    unused_agents = all_agents - used_agents
    if unused_agents:
        print(f"\n## Unused Agents ({len(unused_agents)})")
        for name in sorted(unused_agents):
            print(f"  - {name}")

if all_skills_dir.exists():
    # Skills are directories containing SKILL.md, exclude archive
    all_skills = {p.parent.name for p in all_skills_dir.glob("*/SKILL.md") if p.parent.name != "archive"}
    used_skills = set(skills.keys())
    unused_skills = all_skills - used_skills
    if unused_skills:
        print(f"\n## Unused Skills ({len(unused_skills)})")
        for name in sorted(unused_skills):
            print(f"  - {name}")

if all_commands_dir.exists():
    # Exclude archive directory
    all_commands = {p.stem for p in all_commands_dir.glob("*.md") if p.parent.name != "archive"}
    used_commands = set(commands.keys())
    unused_commands = all_commands - used_commands
    if unused_commands:
        print(f"\n## Unused Commands ({len(unused_commands)})")
        for name in sorted(unused_commands):
            print(f"  - {name}")

PYTHON

echo ""
echo "Data file: $USAGE_FILE"

#!/usr/bin/env bash
# Backup Claude Code configuration files
# Usage: backup-config.sh [component]
#
# Components: settings, hooks, agents, commands, skills, rules, all (default)

set -euo pipefail

CLAUDE_DIR="$HOME/.claude"
BACKUP_DIR="$CLAUDE_DIR/backups"
DATE=$(date +%Y-%m-%d_%H%M%S)
COMPONENT="${1:-all}"

backup_file() {
    local src="$1"
    local dest_dir="$2"
    local name=$(basename "$src")

    if [[ -f "$src" ]]; then
        cp "$src" "$dest_dir/${name}.${DATE}"
        echo "  ✓ $name"
    fi
}

backup_dir_files() {
    local src_dir="$1"
    local dest_dir="$2"
    local pattern="${3:-*.md}"
    local count=0

    shopt -s nullglob
    for f in "$src_dir"/$pattern; do
        [[ -f "$f" ]] || continue
        name=$(basename "$f")
        cp "$f" "$dest_dir/${name}.${DATE}"
        ((count++)) || true
    done
    shopt -u nullglob

    if [[ $count -gt 0 ]]; then
        echo "  ✓ $count files"
    else
        echo "  (no files)"
    fi
}

backup_settings() {
    echo "Settings:"
    backup_file "$CLAUDE_DIR/settings.json" "$BACKUP_DIR/settings"
    [[ -f "$CLAUDE_DIR/settings.local.json" ]] && \
        backup_file "$CLAUDE_DIR/settings.local.json" "$BACKUP_DIR/settings"
}

backup_hooks() {
    echo "Hooks:"
    local count=0
    shopt -s nullglob
    for f in "$CLAUDE_DIR/hooks"/*.py; do
        [[ -f "$f" ]] || continue
        name=$(basename "$f")
        cp "$f" "$BACKUP_DIR/hooks/${name}.${DATE}"
        ((count++)) || true
    done
    shopt -u nullglob
    echo "  ✓ $count files"
}

backup_agents() {
    echo "Agents:"
    backup_dir_files "$CLAUDE_DIR/agents" "$BACKUP_DIR/agents" "*.md"
}

backup_commands() {
    echo "Commands:"
    backup_dir_files "$CLAUDE_DIR/commands" "$BACKUP_DIR/commands" "*.md"
}

backup_skills() {
    echo "Skills:"
    local count=0
    shopt -s nullglob
    for skill_dir in "$CLAUDE_DIR/skills"/*/; do
        [[ -d "$skill_dir" ]] || continue
        [[ "$(basename "$skill_dir")" == "archive" ]] && continue
        skill_name=$(basename "$skill_dir")
        if [[ -f "$skill_dir/SKILL.md" ]]; then
            cp "$skill_dir/SKILL.md" "$BACKUP_DIR/skills/${skill_name}_SKILL.md.${DATE}"
            ((count++)) || true
        fi
    done
    shopt -u nullglob
    echo "  ✓ $count skills"
}

backup_rules() {
    echo "Rules:"
    backup_dir_files "$CLAUDE_DIR/rules" "$BACKUP_DIR/rules" "*.md"
}

echo "╔════════════════════════════════════════╗"
echo "║     Claude Config Backup - $DATE     ║"
echo "╚════════════════════════════════════════╝"
echo ""

case "$COMPONENT" in
    settings) backup_settings ;;
    hooks)    backup_hooks ;;
    agents)   backup_agents ;;
    commands) backup_commands ;;
    skills)   backup_skills ;;
    rules)    backup_rules ;;
    all)
        backup_settings
        backup_hooks
        backup_agents
        backup_commands
        backup_skills
        backup_rules
        ;;
    *)
        echo "Unknown component: $COMPONENT"
        echo "Valid: settings, hooks, agents, commands, skills, rules, all"
        exit 1
        ;;
esac

echo ""
echo "Backups stored in: $BACKUP_DIR"

# Show backup size
total_size=$(du -sh "$BACKUP_DIR" 2>/dev/null | cut -f1)
echo "Total backup size: $total_size"

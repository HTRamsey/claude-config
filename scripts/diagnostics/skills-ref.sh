#!/usr/bin/env bash
# Wrapper for skills-ref CLI (agentskills SDK)
#
# Usage:
#   skills-ref.sh validate <skill-path>
#   skills-ref.sh read <skill-path>
#   skills-ref.sh prompt <skill-path>
#
# Examples:
#   skills-ref.sh validate ~/.claude/skills/pdf
#   skills-ref.sh read ~/.claude/skills/skill-creator
#   skills-ref.sh prompt ~/.claude/skills/  # All skills

set -euo pipefail

VENV_BIN="${HOME}/.claude/data/venv/bin"

usage() {
    echo "Usage: $0 <command> [skill-path]"
    echo ""
    echo "Commands:"
    echo "  validate <path>   Validate a single skill directory"
    echo "  validate-all      Validate all skills in ~/.claude/skills/"
    echo "  read <path>       Read and print skill properties as JSON"
    echo "  prompt <path>     Generate <available_skills> XML for agent prompts"
    echo ""
    echo "Examples:"
    echo "  $0 validate ~/.claude/skills/pdf"
    echo "  $0 validate-all"
    echo "  $0 read ~/.claude/skills/skill-creator"
    exit 1
}

if [[ $# -lt 1 ]]; then
    usage
fi

CMD="$1"
SKILL_PATH="${2:-}"

case "$CMD" in
    validate)
        if [[ -z "$SKILL_PATH" ]]; then
            echo "Error: skill-path required for validate"
            usage
        fi
        "${VENV_BIN}/skills-ref" validate "$SKILL_PATH"
        ;;
    validate-all)
        # Validate all skills in ~/.claude/skills/
        SKILLS_DIR="${HOME}/.claude/skills"
        errors=0
        for skill_dir in "$SKILLS_DIR"/*/; do
            if [[ -f "${skill_dir}SKILL.md" ]]; then
                name=$(basename "$skill_dir")
                if "${VENV_BIN}/skills-ref" validate "$skill_dir" 2>/dev/null; then
                    echo "✓ $name"
                else
                    echo "✗ $name"
                    "${VENV_BIN}/skills-ref" validate "$skill_dir" 2>&1 | sed 's/^/  /'
                    ((errors++)) || true
                fi
            fi
        done
        echo ""
        if [[ $errors -eq 0 ]]; then
            echo "All skills valid!"
        else
            echo "$errors skill(s) with errors"
            exit 1
        fi
        ;;
    read)
        if [[ -z "$SKILL_PATH" ]]; then
            echo "Error: skill-path required for read"
            usage
        fi
        "${VENV_BIN}/skills-ref" read-properties "$SKILL_PATH"
        ;;
    prompt)
        if [[ -z "$SKILL_PATH" ]]; then
            echo "Error: skill-path required for prompt"
            usage
        fi
        "${VENV_BIN}/skills-ref" to-prompt "$SKILL_PATH"
        ;;
    *)
        echo "Unknown command: $CMD"
        usage
        ;;
esac

#!/usr/bin/env bash
# Progressive skill loader - loads skills in tiers to minimize token usage
#
# Usage: skill-loader.sh <skill-name> [tier]
#   tier 1: metadata only (~50 tokens)
#   tier 2: metadata + instructions (~250 tokens)
#   tier 3: full skill (all content)
#
# Example:
#   skill-loader.sh test-driven-development 1  # Quick overview
#   skill-loader.sh test-driven-development 2  # Core instructions
#   skill-loader.sh test-driven-development 3  # Full content

set -euo pipefail

SKILLS_DIR="${HOME}/.claude/skills"

usage() {
    cat <<EOF
Progressive Skill Loader

Usage: $(basename "$0") <skill-name> [tier]

Tiers:
  1  Metadata only (~50 tokens) - triggers, summary
  2  Core instructions (~250 tokens) - essential rules
  3  Full skill (default) - complete documentation

Examples:
  $(basename "$0") test-driven-development 1
  $(basename "$0") systematic-debugging 2
  $(basename "$0") git-workflow           # Full by default
EOF
}

load_skill() {
    local skill="$1"
    local tier="${2:-3}"
    local skill_dir="${SKILLS_DIR}/${skill}"

    if [[ ! -d "$skill_dir" ]]; then
        echo "Error: Skill '$skill' not found in $SKILLS_DIR" >&2
        exit 1
    fi

    case "$tier" in
        1)
            # Tier 1: Metadata only
            if [[ -f "${skill_dir}/metadata.yml" ]]; then
                echo "# ${skill} (Tier 1: Metadata)"
                echo ""
                cat "${skill_dir}/metadata.yml"
            elif [[ -f "${skill_dir}/SKILL.md" ]]; then
                # Extract frontmatter as fallback
                echo "# ${skill} (Tier 1: Extracted)"
                echo ""
                sed -n '/^---$/,/^---$/p' "${skill_dir}/SKILL.md" | head -20
            fi
            ;;
        2)
            # Tier 2: Metadata + instructions
            if [[ -f "${skill_dir}/metadata.yml" ]]; then
                echo "# ${skill} (Tier 2: Instructions)"
                echo ""
                cat "${skill_dir}/metadata.yml"
                echo ""
                echo "---"
                echo ""
            fi

            if [[ -f "${skill_dir}/instructions.md" ]]; then
                cat "${skill_dir}/instructions.md"
            elif [[ -f "${skill_dir}/SKILL.md" ]]; then
                # Extract first 100 lines as fallback
                echo "# Core Instructions"
                echo ""
                head -100 "${skill_dir}/SKILL.md"
            fi
            ;;
        3)
            # Tier 3: Full content
            if [[ -f "${skill_dir}/SKILL.md" ]]; then
                cat "${skill_dir}/SKILL.md"
            fi
            ;;
        *)
            echo "Error: Invalid tier '$tier'. Use 1, 2, or 3." >&2
            exit 1
            ;;
    esac
}

list_skills() {
    echo "Available skills:"
    echo ""
    for skill_dir in "${SKILLS_DIR}"/*/; do
        if [[ -d "$skill_dir" ]]; then
            skill=$(basename "$skill_dir")
            # Check for progressive format
            if [[ -f "${skill_dir}/metadata.yml" ]]; then
                format="progressive"
            else
                format="standard"
            fi
            printf "  %-35s [%s]\n" "$skill" "$format"
        fi
    done
}

# Main
if [[ $# -lt 1 ]]; then
    usage
    exit 1
fi

case "$1" in
    -h|--help|help)
        usage
        ;;
    -l|--list|list)
        list_skills
        ;;
    *)
        load_skill "$1" "${2:-3}"
        ;;
esac

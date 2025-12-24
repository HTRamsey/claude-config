#!/usr/bin/env bash
# Symlink critical user-level rules to current project for subagent inheritance
# Usage: init-project-rules.sh [--all] [--gitignore]
#   --all       Symlink all rules (not just critical ones)
#   --gitignore Add .claude/rules/ to .gitignore

set -e

CLAUDE_USER_RULES="$HOME/.claude/rules"
PROJECT_RULES=".claude/rules"

# Critical rules that subagents should inherit
CRITICAL_RULES=(
    "01-style.md"           # Response style, conciseness
    "02-verification.md"    # Always verify before completion
    "03-security-coding.md" # Security-first coding
    "04-tool-optimization.md" # Tool usage patterns
)

# All rules (if --all flag)
ALL_RULES=(
    "01-style.md"
    "02-verification.md"
    "03-security-coding.md"
    "04-tool-optimization.md"
    "05-skill-usage.md"
    "06-scripts.md"
    "07-modern-tools.md"
    "08-general.md"
    "09-context-guidelines.md"
)

# Parse arguments
USE_ALL=false
ADD_GITIGNORE=false
for arg in "$@"; do
    case $arg in
        --all) USE_ALL=true ;;
        --gitignore) ADD_GITIGNORE=true ;;
        -h|--help)
            echo "Usage: init-project-rules.sh [--all] [--gitignore]"
            echo "  --all       Symlink all rules (not just critical ones)"
            echo "  --gitignore Add .claude/rules/ to .gitignore"
            exit 0
            ;;
    esac
done

# Select rules to symlink
if $USE_ALL; then
    RULES=("${ALL_RULES[@]}")
else
    RULES=("${CRITICAL_RULES[@]}")
fi

# Check we're in a git repo or have a .claude directory
if [[ ! -d ".git" && ! -d ".claude" ]]; then
    echo "Warning: Not in a git repo and no .claude directory exists."
    read -p "Create .claude/rules anyway? [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Create project rules directory
mkdir -p "$PROJECT_RULES"

# Symlink each rule
LINKED=0
SKIPPED=0
for rule in "${RULES[@]}"; do
    src="$CLAUDE_USER_RULES/$rule"
    dst="$PROJECT_RULES/$rule"

    if [[ ! -f "$src" ]]; then
        echo "Skip: $rule (not found in $CLAUDE_USER_RULES)"
        ((SKIPPED++))
        continue
    fi

    if [[ -L "$dst" ]]; then
        # Already a symlink - check if pointing to right place
        if [[ "$(readlink "$dst")" == "$src" ]]; then
            echo "OK:   $rule (already linked)"
        else
            echo "Skip: $rule (symlink exists, points elsewhere)"
            ((SKIPPED++))
        fi
        continue
    fi

    if [[ -f "$dst" ]]; then
        echo "Skip: $rule (regular file exists, won't overwrite)"
        ((SKIPPED++))
        continue
    fi

    ln -s "$src" "$dst"
    echo "Link: $rule"
    ((LINKED++))
done

# Optionally add to .gitignore
if $ADD_GITIGNORE && [[ -f ".gitignore" ]]; then
    if ! grep -q "^\.claude/rules/$" .gitignore 2>/dev/null; then
        echo ".claude/rules/" >> .gitignore
        echo "Added .claude/rules/ to .gitignore"
    fi
elif $ADD_GITIGNORE && [[ -d ".git" ]]; then
    echo ".claude/rules/" >> .gitignore
    echo "Created .gitignore with .claude/rules/"
fi

echo ""
echo "Done: $LINKED linked, $SKIPPED skipped"
echo "Subagents in this project will now inherit these rules."

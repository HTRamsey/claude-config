#!/usr/bin/env bash
# smart-diff.sh - Token-efficient git diff with multiple engines
# Usage: smart-diff.sh [--structural] [git-diff-args...]
#
# Engines (with fallback chain):
#   Default:      delta → compress-diff.sh → git diff
#   --structural: difftastic (AST-aware) → delta → git diff
#
# Consolidates smart-diff.sh and smart-difft.sh functionality

set -e

# Check for structural mode flag
STRUCTURAL=false
if [[ "$1" == "--structural" || "$1" == "-s" ]]; then
    STRUCTURAL=true
    shift
fi

# Find difftastic
find_difft() {
    if command -v difft &>/dev/null; then
        echo "difft"
    elif [[ -x "$HOME/.cargo/bin/difft" ]]; then
        echo "$HOME/.cargo/bin/difft"
    fi
}

# Structural diff mode (uses difftastic)
if [[ "$STRUCTURAL" == true ]]; then
    DIFFT=$(find_difft)
    if [[ -n "$DIFFT" ]]; then
        GIT_EXTERNAL_DIFF="$DIFFT" git diff "$@" 2>/dev/null | head -200
        exit 0
    fi
    echo "# difftastic not found, falling back to delta" >&2
fi

# Standard diff mode with delta
if command -v delta &>/dev/null; then
    git diff "$@" | delta \
        --no-gitconfig \
        --line-numbers \
        --side-by-side=false \
        --width=80 \
        --tabs=2 \
        --file-style='bold yellow' \
        --hunk-header-style='omit' \
        --minus-style='red' \
        --plus-style='green' \
        2>/dev/null | head -200
elif [[ -n "$(find_difft)" ]]; then
    # Fall back to difftastic if delta not available
    DIFFT=$(find_difft)
    GIT_EXTERNAL_DIFF="$DIFFT" git diff "$@" 2>/dev/null | head -200
elif [[ -f "$HOME/.claude/scripts/compress-diff.sh" ]]; then
    # Fall back to compression script
    git diff "$@" | "$HOME/.claude/scripts/compress-diff.sh"
else
    # Basic fallback
    git diff --stat "$@" 2>/dev/null
    echo "---"
    git diff "$@" 2>/dev/null | head -100
fi

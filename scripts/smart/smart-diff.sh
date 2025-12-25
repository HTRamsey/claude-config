#!/usr/bin/env bash
# smart-diff.sh - Token-efficient diff with multiple engines
# Usage: smart-diff.sh [--structural|-s] [git-diff-args...]
#    or: smart-diff.sh <file1> <file2>   # Direct file comparison
#
# Engines (with fallback chain):
#   Default:      delta → compress.sh --type diff → git diff
#   --structural: difftastic (AST-aware) → delta → git diff
#   File mode:    difft → diff -u

set -euo pipefail
source "$HOME/.claude/scripts/lib/common.sh"

# Direct file comparison mode (two files as arguments)
if [[ -f "$1" && -f "$2" && $# -eq 2 ]]; then
    DIFFT=$(find_difft)
    if [[ -n "$DIFFT" ]]; then
        exec $DIFFT --color=never "$1" "$2" 2>/dev/null | head -200
    else
        exec diff -u "$1" "$2" 2>/dev/null | head -100
    fi
fi

# Check for structural mode flag
STRUCTURAL=false
if [[ "$1" == "--structural" || "$1" == "-s" ]]; then
    STRUCTURAL=true
    shift
fi

# Structural diff mode (uses difftastic)
if [[ "$STRUCTURAL" == true ]]; then
    DIFFT=$(find_difft)
    if [[ -n "$DIFFT" ]]; then
        GIT_EXTERNAL_DIFF="$DIFFT" git diff "$@" 2>/dev/null | head -200
        exit 0
    fi
    echo "# difftastic not found, falling back to delta" >&2
fi

# Cache tool lookups
DIFFT=$(find_difft)
DELTA=$(find_delta)

# Standard diff mode with delta
if [[ -n "$DELTA" ]]; then
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
elif [[ -n "$DIFFT" ]]; then
    # Fall back to difftastic if delta not available
    GIT_EXTERNAL_DIFF="$DIFFT" git diff "$@" 2>/dev/null | head -200
elif [[ -f "$HOME/.claude/scripts/compress/compress.sh" ]]; then
    # Fall back to compression script
    git diff "$@" | "$HOME/.claude/scripts/compress/compress.sh" --type diff
else
    # Basic fallback
    git diff --stat "$@" 2>/dev/null
    echo "---"
    git diff "$@" 2>/dev/null | head -100
fi

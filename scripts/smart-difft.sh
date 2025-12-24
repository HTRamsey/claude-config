#!/usr/bin/env bash
# smart-difft.sh - Structural diff wrapper (calls smart-diff.sh --structural)
# Usage: smart-difft.sh [git-diff-args...]
#    or: smart-difft.sh <file1> <file2>
#
# This is now a thin wrapper around smart-diff.sh --structural
# For direct file comparison, use: difft file1 file2

# Check if comparing two files directly (not git)
if [[ -f "$1" && -f "$2" ]]; then
    # Direct file comparison - use difft directly
    DIFFT=""
    if command -v difft &>/dev/null; then
        DIFFT="difft"
    elif [[ -x "$HOME/.cargo/bin/difft" ]]; then
        DIFFT="$HOME/.cargo/bin/difft"
    fi

    if [[ -n "$DIFFT" ]]; then
        exec $DIFFT --color=never "$1" "$2" 2>/dev/null | head -200
    else
        exec diff -u "$1" "$2" 2>/dev/null | head -100
    fi
else
    # Git diff mode
    exec "$HOME/.claude/scripts/smart-diff.sh" --structural "$@"
fi

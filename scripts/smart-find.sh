#!/usr/bin/env bash
# smart-find.sh - Token-efficient file finding using fd
# Usage: smart-find.sh [pattern] [path] [limit]
# fd is faster and has better defaults than find (respects .gitignore)

set -e

pattern="${1:-}"
path="${2:-.}"
limit="${3:-30}"

# Find fd (cargo or system)
FD=""
if command -v fd &>/dev/null; then
    FD="fd"
elif [[ -x "$HOME/.cargo/bin/fd" ]]; then
    FD="$HOME/.cargo/bin/fd"
elif command -v fdfind &>/dev/null; then
    FD="fdfind"
fi

if [[ -n "$FD" ]]; then
    if [[ -n "$pattern" ]]; then
        # fd syntax: fd [pattern] [path]
        $FD "$pattern" "$path" --color=never 2>/dev/null | head -"$limit"
    else
        # List all files - use . as match-all pattern
        $FD . "$path" --color=never --type f 2>/dev/null | head -"$limit"
    fi
else
    # Fallback to find
    if [[ -n "$pattern" ]]; then
        find "$path" -name "*$pattern*" -type f 2>/dev/null | head -"$limit"
    else
        find "$path" -type f 2>/dev/null | head -"$limit"
    fi
fi

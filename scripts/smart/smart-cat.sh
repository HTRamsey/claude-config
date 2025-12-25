#!/usr/bin/env bash
# smart-cat.sh - Token-efficient file viewing using bat
# Usage: smart-cat.sh <file> [line-range]
# bat provides syntax highlighting and line numbers built-in

set -euo pipefail
source "$HOME/.claude/scripts/lib/common.sh"

file="$1"
range="${2:-}"

if [[ -z "$file" ]]; then
    echo "Usage: smart-cat.sh <file> [start:end]"
    echo "Example: smart-cat.sh src/main.py 10:50"
    exit 1
fi

BAT=$(find_bat)

if [[ -n "$BAT" ]]; then
    opts="--style=numbers,changes --color=never --paging=never"

    if [[ -n "$range" ]]; then
        $BAT $opts --line-range "$range" "$file" 2>/dev/null
    else
        # For large files, show first 100 lines
        line_count=$(wc -l < "$file" 2>/dev/null || echo "0")
        if [[ "$line_count" -gt 100 ]]; then
            echo "# File has $line_count lines, showing first 100"
            $BAT $opts --line-range ":100" "$file" 2>/dev/null
            echo "# ... truncated ($((line_count - 100)) more lines)"
        else
            $BAT $opts "$file" 2>/dev/null
        fi
    fi
else
    # Fallback to cat with line numbers
    if [[ -n "$range" ]]; then
        start="${range%:*}"
        end="${range#*:}"
        sed -n "${start},${end}p" "$file" 2>/dev/null | nl -ba
    else
        head -100 "$file" 2>/dev/null | nl -ba
    fi
fi

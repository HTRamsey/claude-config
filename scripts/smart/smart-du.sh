#!/usr/bin/env bash
# smart-du.sh - Token-efficient disk usage using dust
# Usage: smart-du.sh [path] [depth]
# dust provides compact, visual disk usage output

set -e

path="${1:-.}"
depth="${2:-3}"

# Find dust (cargo or system)
DUST=""
if command -v dust &>/dev/null; then
    DUST="dust"
elif [[ -x "$HOME/.cargo/bin/dust" ]]; then
    DUST="$HOME/.cargo/bin/dust"
fi

if [[ -n "$DUST" ]]; then
    # dust with limited depth and no color for smaller output
    $DUST -d "$depth" -n 20 "$path" 2>/dev/null
else
    # Fallback to du
    du -h --max-depth="$depth" "$path" 2>/dev/null | sort -hr | head -20
fi

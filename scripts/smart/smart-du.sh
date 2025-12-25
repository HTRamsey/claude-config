#!/usr/bin/env bash
# smart-du.sh - Token-efficient disk usage using dust
# Usage: smart-du.sh [path] [depth]
# dust provides compact, visual disk usage output

set -euo pipefail
source "$HOME/.claude/scripts/lib/common.sh"

path="${1:-.}"
depth="${2:-3}"

DUST=$(find_dust)

if [[ -n "$DUST" ]]; then
    # dust with limited depth and no color for smaller output
    $DUST -d "$depth" -n 20 "$path" 2>/dev/null
else
    # Fallback to du
    du -h --max-depth="$depth" "$path" 2>/dev/null | sort -hr | head -20
fi

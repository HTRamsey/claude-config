#!/usr/bin/env bash
# smart-ls.sh - Token-efficient directory listing with tree support
# Usage: smart-ls.sh [path] [depth] [pattern]
#
# Consolidates smart-ls.sh and smart-tree.sh functionality:
#   depth=1  -> compact listing (default)
#   depth>1  -> tree view with git-ignore
#   pattern  -> filter tree output by regex
#
# 75-87% smaller output than ls -la / tree

set -euo pipefail
source "$HOME/.claude/scripts/lib/common.sh"

path="${1:-.}"
depth="${2:-1}"
pattern="${3:-}"

EZA=$(find_eza)
if [[ -n "$EZA" ]]; then
    if [[ "$depth" -gt 1 ]]; then
        # Tree mode with git-ignore
        opts="--tree --level=$depth --icons=never --no-permissions --no-user --no-time --git-ignore"
        if [[ -n "$pattern" ]]; then
            $EZA $opts "$path" 2>/dev/null | grep -E "$pattern|^[│├└─ ]*$" | head -100
        else
            $EZA $opts "$path" 2>/dev/null | head -100
        fi
    else
        # Compact one-line listing
        $EZA --oneline --group-directories-first "$path" 2>/dev/null
    fi
elif has_command lsd && [[ "$depth" -gt 1 ]]; then
    # lsd fallback for tree mode
    lsd --tree --depth="$depth" --icon=never "$path" 2>/dev/null | head -100
else
    # Standard fallback
    if [[ "$depth" -gt 1 ]]; then
        find "$path" -maxdepth "$depth" \( -type f -o -type d \) 2>/dev/null | \
            grep -v node_modules | grep -v __pycache__ | grep -v '.git/' | \
            sort | head -100
    else
        ls -1 "$path" 2>/dev/null
    fi
fi

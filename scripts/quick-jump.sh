#!/usr/bin/env bash
# quick-jump.sh - Get best matching directory using zoxide
# Usage: quick-jump.sh <query>
# Returns the path without changing directory (for Claude to use)

set -e

query="$1"

if [[ -z "$query" ]]; then
    echo "Usage: quick-jump.sh <query>"
    echo "Returns best matching directory path"
    exit 1
fi

if command -v zoxide &>/dev/null; then
    # Query zoxide database for best match
    zoxide query "$query" 2>/dev/null || echo "No match found for: $query"
else
    # Fallback: search common locations
    find ~ -maxdepth 4 -type d -name "*$query*" 2>/dev/null | head -5
fi

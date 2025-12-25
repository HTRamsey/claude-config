#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat << 'EOF'
Usage: quick-jump.sh <query>

Get best matching directory using zoxide.
Returns the path without changing directory (for Claude to use).

Options:
  -h, --help    Show this help

Examples:
  quick-jump.sh myproject
  quick-jump.sh frontend
EOF
    exit 0
}

[[ "${1:-}" =~ ^(-h|--help)$ ]] && usage

query="$1"

if [[ -z "$query" ]]; then
    echo "Error: Query required"
    echo "Run: quick-jump.sh --help"
    exit 1
fi

if command -v zoxide &>/dev/null; then
    # Query zoxide database for best match
    zoxide query "$query" 2>/dev/null || echo "No match found for: $query"
else
    # Fallback: search common locations
    find ~ -maxdepth 4 -type d -name "*$query*" 2>/dev/null | head -5
fi

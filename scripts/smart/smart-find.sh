#!/usr/bin/env bash
# smart-find.sh - Token-efficient file finding using fd
# Usage: smart-find.sh [pattern] [path] [limit]
# fd is faster and has better defaults than find (respects .gitignore)

set -euo pipefail
source "$HOME/.claude/scripts/lib/common.sh"

usage() {
    echo "Usage: $(basename "$0") [pattern] [path] [limit]"
    echo ""
    echo "Token-efficient file finding using fd (with fallback to find)"
    echo ""
    echo "Options:"
    echo "  -h, --help    Show this help message"
    echo ""
    echo "Arguments:"
    echo "  pattern       File pattern to search for (default: all files)"
    echo "  path          Directory to search in (default: .)"
    echo "  limit         Maximum number of results (default: 30)"
    echo ""
    echo "Features:"
    echo "  - Uses fd if available (faster, respects .gitignore)"
    echo "  - Falls back to find if fd not available"
    echo "  - Auto-limits output to prevent token waste"
    echo ""
    echo "Examples:"
    echo "  $(basename "$0") '*.py'"
    echo "  $(basename "$0") 'test' ./src 50"
    echo "  $(basename "$0") '' . 100    # List all files"
}

[[ "${1:-}" == "-h" || "${1:-}" == "--help" ]] && { usage; exit 0; }

pattern="${1:-}"
path="${2:-.}"
limit="${3:-30}"

FD=$(find_fd)

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

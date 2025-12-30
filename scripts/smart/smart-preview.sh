#!/usr/bin/env bash
# smart-preview.sh - Quick file preview showing head, tail, and structure
#
# Usage:
#   smart-preview.sh <file>
#   smart-preview.sh -n <lines> <file>
#
# This is a convenience wrapper for: smart-view.sh <file> preview
# Shows first/last N lines plus structural overview (classes, functions)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

show_help() {
    cat << 'EOF'
smart-preview.sh - Quick file preview showing head, tail, and structure

Usage:
  smart-preview.sh <file>
  smart-preview.sh -n <lines> <file>    Customize head/tail line count

Examples:
  smart-preview.sh src/main.py          # Preview with 10 lines head/tail
  smart-preview.sh -n 20 large.cpp      # Preview with 20 lines head/tail

Equivalent to: smart-view.sh <file> preview

For full options, see: smart-view.sh --help
EOF
    exit 0
}

# Parse arguments
LINES=""
FILE=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help) show_help ;;
        -n) LINES="$2"; shift 2 ;;
        *)
            FILE="$1"; shift ;;
    esac
done

if [[ -z "$FILE" ]]; then
    echo "Usage: smart-preview.sh <file>"
    echo "Try: smart-preview.sh --help"
    exit 1
fi

# Delegate to smart-view.sh with preview mode
if [[ -n "$LINES" ]]; then
    exec "$SCRIPT_DIR/smart-view.sh" -n "$LINES" "$FILE" preview
else
    exec "$SCRIPT_DIR/smart-view.sh" "$FILE" preview
fi

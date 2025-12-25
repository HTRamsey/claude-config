#!/usr/bin/env bash
# smart-replace.sh - Token-efficient search and replace using sd
# Usage: smart-replace.sh <pattern> <replacement> <file-or-glob>
# sd has simpler syntax than sed - no escaping needed for / or special chars

set -euo pipefail

# Source common utilities
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../lib/common.sh"

usage() {
    echo "Usage: $(basename "$0") <pattern> <replacement> <file-or-glob>"
    echo ""
    echo "Token-efficient search and replace using sd"
    echo ""
    echo "Options:"
    echo "  -h, --help    Show this help message"
    echo ""
    echo "Arguments:"
    echo "  pattern       Text pattern to search for"
    echo "  replacement   Replacement text"
    echo "  target        File path or glob pattern"
    echo ""
    echo "Features:"
    echo "  - Uses sd if available (simpler syntax than sed)"
    echo "  - No escaping needed for / or special characters"
    echo "  - Preview mode by default (shows changes without applying)"
    echo "  - Falls back to sed if sd not available"
    echo ""
    echo "Examples:"
    echo "  $(basename "$0") 'oldFunc' 'newFunc' 'src/**/*.py'"
    echo "  $(basename "$0") 'TODO' 'DONE' 'notes.txt'"
}

[[ "${1:-}" == "-h" || "${1:-}" == "--help" ]] && { usage; exit 0; }

pattern="${1:-}"
replacement="${2:-}"
target="${3:-}"

if [[ -z "$pattern" || -z "$replacement" || -z "$target" ]]; then
    usage
    exit 1
fi

SD=$(find_sd) || SD=""

if [[ -n "$SD" ]]; then
    # sd handles literal strings by default, use -f for fixed strings
    if [[ -d "$target" ]] || [[ "$target" == *"*"* ]]; then
        # Glob pattern - find files first
        file_pattern="${target##*/}"
        if [[ "$target" == *"/"* ]]; then
            search_dir="${target%/*}"
        else
            search_dir="."
        fi

        # Use find directly without eval
        echo "Files to modify:"
        find "$search_dir" -type f -name "$file_pattern" 2>/dev/null | head -20
        echo ""
        echo "Preview (first match):"
        first_file=$(find "$search_dir" -type f -name "$file_pattern" 2>/dev/null | head -1)
        if [[ -n "$first_file" ]]; then
            $SD "$pattern" "$replacement" "$first_file" --preview 2>/dev/null | head -10
        fi
    else
        # Single file
        echo "Preview:"
        $SD "$pattern" "$replacement" "$target" --preview 2>/dev/null | head -20
        echo ""
        echo "Run without --preview to apply changes"
    fi
else
    # Fallback to sed
    log_warn "sd not available, using sed"
    echo "Preview:"
    sed -n "s/$pattern/$replacement/gp" "$target" 2>/dev/null | head -20
fi

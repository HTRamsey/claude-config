#!/usr/bin/env bash
# smart-replace.sh - Token-efficient search and replace using sd
# Usage: smart-replace.sh <pattern> <replacement> <file-or-glob>
# sd has simpler syntax than sed - no escaping needed for / or special chars

set -e

pattern="$1"
replacement="$2"
target="$3"

if [[ -z "$pattern" || -z "$replacement" || -z "$target" ]]; then
    echo "Usage: smart-replace.sh <pattern> <replacement> <file-or-glob>"
    echo "Example: smart-replace.sh 'oldFunc' 'newFunc' 'src/**/*.py'"
    exit 1
fi

if command -v sd &>/dev/null; then
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
            sd "$pattern" "$replacement" "$first_file" --preview 2>/dev/null | head -10
        fi
    else
        # Single file
        echo "Preview:"
        sd "$pattern" "$replacement" "$target" --preview 2>/dev/null | head -20
        echo ""
        echo "Run without --preview to apply changes"
    fi
else
    # Fallback to sed
    echo "sd not available, using sed"
    echo "Preview:"
    sed -n "s/$pattern/$replacement/gp" "$target" 2>/dev/null | head -20
fi

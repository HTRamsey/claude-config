#!/usr/bin/env bash
# Find files related to a given file (imports/includes and reverse dependencies)
# Usage: find-related.sh <file> [search_dir]

set -euo pipefail

file="${1:-}"
search_dir="${2:-.}"

if [[ -z "$file" || ! -f "$file" ]]; then
    echo "Usage: find-related.sh <file> [search_dir]"
    exit 1
fi

filename=$(basename "$file")
name_no_ext="${filename%.*}"
ext="${filename##*.}"

echo "=== Related files for: $file ==="
echo ""

# What this file imports/includes
echo "## This file imports:"
case "$ext" in
    py)
        grep -h "^import \|^from .* import" "$file" 2>/dev/null | sed 's/import //;s/from //;s/ import.*//' | sort -u || true
        ;;
    ts|tsx|js|jsx)
        grep -h "^import .* from \|require(" "$file" 2>/dev/null | sed "s/.*from ['\"]//;s/['\"].*//;s/.*require(['\"]//;s/['\"]).*//;" | sort -u || true
        ;;
    cpp|cc|c|h|hpp)
        grep -h "^#include" "$file" 2>/dev/null | sed 's/#include [<"]//;s/[>"]$//' | sort -u || true
        ;;
    go)
        sed -n '/^import/,/)/p' "$file" 2>/dev/null | grep -v "import\|)\|^$" | tr -d '\t"' | sort -u || true
        ;;
    *)
        echo "(import detection not supported for .$ext)"
        ;;
esac

echo ""
echo "## Files that reference this file:"

# Find files that import/include this file
{
    # Search for the filename
    rg -l "import.*$name_no_ext\|from.*$name_no_ext\|require.*$name_no_ext\|#include.*$filename" "$search_dir" \
        --type-add 'code:*.{py,ts,tsx,js,jsx,cpp,cc,c,h,hpp,go,rs,java,kt}' \
        -t code 2>/dev/null || true

    # Also search for the full filename in includes
    rg -l "$filename" "$search_dir" \
        --type-add 'code:*.{py,ts,tsx,js,jsx,cpp,cc,c,h,hpp,go,rs,java,kt}' \
        -t code 2>/dev/null || true
} | grep -v "^$file$" | sort -u | head -30

echo ""
echo "## Files with similar names:"
fd "$name_no_ext" "$search_dir" --type f 2>/dev/null | grep -v "^$file$" | head -10 || true

#!/usr/bin/env bash
# Summarize large files - show structure without full content
# Usage: summarize-file.sh <file> [max_lines]

set -euo pipefail
source "$HOME/.claude/scripts/lib/common.sh"

file="${1:-}"
max_lines="${2:-50}"

if [[ -z "$file" || ! -f "$file" ]]; then
    echo "Usage: summarize-file.sh <file> [max_lines]"
    exit 1
fi

lang=$(detect_language "$file")
lines=$(wc -l < "$file")
size=$(du -h "$file" | cut -f1)

echo "=== $file ($lines lines, $size) ==="
echo ""

case "$lang" in
    python)
        echo "## Classes & Functions"
        grep -n "^class \|^def \|^async def " "$file" 2>/dev/null | head -"$max_lines" || true
        echo ""
        echo "## Imports"
        grep -n "^import \|^from .* import" "$file" 2>/dev/null | head -20 || true
        ;;
    typescript|javascript)
        echo "## Exports & Classes"
        grep -n "^export \|^class \|^interface \|^type \|^function \|^const .* = (" "$file" 2>/dev/null | head -"$max_lines" || true
        echo ""
        echo "## Imports"
        grep -n "^import " "$file" 2>/dev/null | head -20 || true
        ;;
    c|cpp)
        echo "## Classes & Functions"
        grep -n "^class \|^struct \|^enum \|^[a-zA-Z_].*(.*)[ ]*{$\|^[a-zA-Z_].*(.*)[ ]*$" "$file" 2>/dev/null | head -"$max_lines" || true
        echo ""
        echo "## Includes"
        grep -n "^#include" "$file" 2>/dev/null | head -20 || true
        ;;
    java|kotlin)
        echo "## Classes & Methods"
        grep -n "^public \|^private \|^protected \|^class \|^interface " "$file" 2>/dev/null | head -"$max_lines" || true
        echo ""
        echo "## Imports"
        grep -n "^import " "$file" 2>/dev/null | head -20 || true
        ;;
    go)
        echo "## Functions & Types"
        grep -n "^func \|^type " "$file" 2>/dev/null | head -"$max_lines" || true
        echo ""
        echo "## Imports"
        sed -n '/^import/,/)/p' "$file" 2>/dev/null | head -20 || true
        ;;
    rust)
        echo "## Functions & Structs"
        grep -n "^pub \|^fn \|^struct \|^enum \|^impl " "$file" 2>/dev/null | head -"$max_lines" || true
        echo ""
        echo "## Use statements"
        grep -n "^use " "$file" 2>/dev/null | head -20 || true
        ;;
    qml)
        echo "## Components & Properties"
        grep -n "^[A-Z][a-zA-Z]* {$\|^    [a-z]*:\|^    function \|^    signal " "$file" 2>/dev/null | head -"$max_lines" || true
        ;;
    *)
        echo "## Structure (first/last $((max_lines/2)) lines)"
        head -"$((max_lines/2))" "$file"
        echo "..."
        tail -"$((max_lines/2))" "$file"
        ;;
esac

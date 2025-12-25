#!/usr/bin/env bash
# smart-preview.sh - Smart preview of large files
#
# Usage:
#   smart-preview.sh largefile.log
#   smart-preview.sh --lines 20 bigdata.json
#   smart-preview.sh --structure src/app.ts
#
# Shows: Head, tail, structure (functions/classes), and size info
# Saves: 90%+ tokens while providing useful context

set -euo pipefail
source "$HOME/.claude/scripts/lib/common.sh"

LINES=10
STRUCTURE=false
FILE=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --lines|-n)
            LINES="$2"
            shift 2
            ;;
        --structure|-s)
            STRUCTURE=true
            shift
            ;;
        *)
            FILE="$1"
            shift
            ;;
    esac
done

if [[ -z "$FILE" ]] || [[ ! -f "$FILE" ]]; then
    echo "Usage: smart-preview.sh [--lines N] [--structure] file"
    exit 1
fi

TOTAL_LINES=$(wc -l < "$FILE")
TOTAL_SIZE=$(stat -c%s "$FILE" 2>/dev/null || stat -f%z "$FILE" 2>/dev/null)
TOTAL_KB=$((TOTAL_SIZE / 1024))

echo "=== FILE INFO ==="
echo "Path: $FILE"
echo "Size: ${TOTAL_KB}KB ($TOTAL_SIZE bytes)"
echo "Lines: $TOTAL_LINES"
echo ""

# Detect file type for structure extraction
detect_structure() {
    local file="$1"
    case "$file" in
        *.py)
            echo "=== STRUCTURE (Python) ==="
            grep -nE "^(class |def |async def )" "$file" | head -30
            ;;
        *.ts|*.tsx|*.js|*.jsx)
            echo "=== STRUCTURE (JS/TS) ==="
            grep -nE "^(export |function |class |const [A-Z]|interface |type )" "$file" | head -30
            ;;
        *.go)
            echo "=== STRUCTURE (Go) ==="
            grep -nE "^(func |type .* (struct|interface))" "$file" | head -30
            ;;
        *.rs)
            echo "=== STRUCTURE (Rust) ==="
            grep -nE "^(pub |fn |struct |enum |trait |impl )" "$file" | head -30
            ;;
        *.java)
            echo "=== STRUCTURE (Java) ==="
            grep -nE "^(public |private |protected |class |interface )" "$file" | head -30
            ;;
        *.c|*.cpp|*.h|*.hpp)
            echo "=== STRUCTURE (C/C++) ==="
            grep -nE "^(struct |class |enum |void |int |char |bool |auto |template)" "$file" | head -30
            ;;
        *.json)
            echo "=== STRUCTURE (JSON keys) ==="
            grep -oE '"[^"]+":' "$file" | sort -u | head -30
            ;;
        *.yaml|*.yml)
            echo "=== STRUCTURE (YAML top-level) ==="
            grep -nE "^[a-zA-Z_]+" "$file" | head -30
            ;;
        *.md)
            echo "=== STRUCTURE (Markdown headings) ==="
            grep -nE "^#{1,4} " "$file" | head -30
            ;;
        *.log)
            echo "=== LOG LEVELS ==="
            echo "Errors: $(grep -ciE "(error|fatal|critical)" "$file" || echo 0)"
            echo "Warnings: $(grep -ci "warn" "$file" || echo 0)"
            echo "Info: $(grep -ci "info" "$file" || echo 0)"
            ;;
        *)
            echo "=== STRUCTURE (generic) ==="
            grep -nE "^[A-Z]|^\[|^#" "$file" | head -20
            ;;
    esac
}

echo "=== HEAD (first $LINES lines) ==="
head -n "$LINES" "$FILE"

if [[ $TOTAL_LINES -gt $((LINES * 3)) ]]; then
    echo ""
    echo "[... $((TOTAL_LINES - LINES * 2)) lines omitted ...]"
    echo ""
    echo "=== TAIL (last $LINES lines) ==="
    tail -n "$LINES" "$FILE"
fi

if [[ "$STRUCTURE" == "true" ]] || [[ $TOTAL_LINES -gt 100 ]]; then
    echo ""
    detect_structure "$FILE"
fi

PREVIEW_LINES=$((LINES * 2 + 30))
if [[ $PREVIEW_LINES -gt $TOTAL_LINES ]]; then
    PREVIEW_LINES=$TOTAL_LINES
fi
echo ""
if [[ $TOTAL_LINES -gt 0 ]]; then
    echo "[Previewed ~$PREVIEW_LINES of $TOTAL_LINES lines ($(( (PREVIEW_LINES * 100) / TOTAL_LINES ))%)]"
else
    echo "[Empty file]"
fi

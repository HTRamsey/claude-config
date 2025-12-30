#!/usr/bin/env bash
# smart-view.sh - Unified intelligent file viewer
#
# Usage:
#   smart-view.sh <file> [mode]
#   smart-view.sh --help
#
# Modes:
#   auto      Auto-select based on file size (default)
#   full      Full content with syntax highlighting
#   summary   Classes, functions, imports only
#   preview   Head/tail with structure
#   structure Structure only (no content)
#
# Auto mode thresholds:
#   <100 lines   → full content
#   100-500      → summary
#   >500         → preview
#
# Special handling: JSON, YAML, logs, markdown

set -euo pipefail
source "$HOME/.claude/scripts/lib/common.sh"

# Thresholds
SMALL_THRESHOLD=100
LARGE_THRESHOLD=500

show_help() {
    cat << 'EOF'
smart-view.sh - Unified intelligent file viewer

Usage:
  smart-view.sh <file> [mode]
  smart-view.sh -n <lines> <file>    Limit output lines
  smart-view.sh -r <start:end> <file> Show line range

Modes:
  auto      Auto-select based on file size (default)
  full      Full content with syntax highlighting
  summary   Show classes, functions, imports
  preview   Head/tail with structure info
  structure Structure only, no content

Examples:
  smart-view.sh src/main.py           # Auto mode
  smart-view.sh src/main.py summary   # Force summary
  smart-view.sh -r 50:100 large.py    # Lines 50-100
  smart-view.sh config.json           # Pretty-print JSON

EOF
    exit 0
}

# Parse arguments
MODE="auto"
LINES=""
RANGE=""
FILE=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help) show_help ;;
        -n) LINES="$2"; shift 2 ;;
        -r|--range) RANGE="$2"; shift 2 ;;
        auto|full|summary|preview|structure)
            MODE="$1"; shift ;;
        *)
            FILE="$1"; shift ;;
    esac
done

if [[ -z "$FILE" ]]; then
    echo "Usage: smart-view.sh <file> [mode]"
    echo "Try: smart-view.sh --help"
    exit 1
fi

if [[ ! -f "$FILE" ]]; then
    echo "Error: File not found: $FILE"
    exit 1
fi

# Get file info
TOTAL_LINES=$(wc -l < "$FILE" 2>/dev/null || echo "0")
TOTAL_SIZE=$(stat -c%s "$FILE" 2>/dev/null || stat -f%z "$FILE" 2>/dev/null || echo "0")
SIZE_KB=$((TOTAL_SIZE / 1024))
LANG=$(detect_language "$FILE")
BAT=$(find_bat)

# Common structure patterns by language (shared between summary and structure views)
# Returns: pattern for grep -nE
get_structure_pattern() {
    local lang="$1"
    case "$lang" in
        python)      echo "^(class |def |async def )" ;;
        typescript|javascript) echo "^(export |function |class |interface |type |const .* = \\()" ;;
        c|cpp)       echo "^(struct |class |enum |void |int |char |bool |auto |[a-zA-Z_].*\\(.*\\)[ ]*\\{$)" ;;
        go)          echo "^(func |type )" ;;
        rust)        echo "^(pub |fn |struct |enum |trait |impl )" ;;
        java|kotlin) echo "^(public |private |protected |class |interface )" ;;
        qml)         echo "^[A-Z][a-zA-Z]* \\{$|^    [a-z]*:|^    function |^    signal " ;;
        bash)        echo "^[a-zA-Z_][a-zA-Z0-9_]*\\(\\) \\{" ;;
        *)           echo "^[A-Z]|^#|^function |^def |^class " ;;
    esac
}

# Auto-select mode based on size
if [[ "$MODE" == "auto" ]]; then
    if [[ $TOTAL_LINES -lt $SMALL_THRESHOLD ]]; then
        MODE="full"
    elif [[ $TOTAL_LINES -lt $LARGE_THRESHOLD ]]; then
        MODE="summary"
    else
        MODE="preview"
    fi
fi

# Header
print_file_info() {
    echo "=== $FILE ==="
    echo "Lines: $TOTAL_LINES | Size: ${SIZE_KB}KB | Lang: $LANG | Mode: $MODE"
    echo ""
}

# Full content with syntax highlighting
view_full() {
    if [[ -n "$BAT" ]]; then
        local opts="--style=numbers,changes --color=never --paging=never"
        if [[ -n "$RANGE" ]]; then
            $BAT $opts --line-range "$RANGE" "$FILE"
        elif [[ -n "$LINES" ]]; then
            $BAT $opts "$FILE" | head -"$LINES"
        else
            $BAT $opts "$FILE"
        fi
    else
        if [[ -n "$RANGE" ]]; then
            local start="${RANGE%:*}"
            local end="${RANGE#*:}"
            sed -n "${start},${end}p" "$FILE" | nl -ba
        elif [[ -n "$LINES" ]]; then
            head -"$LINES" "$FILE" | nl -ba
        else
            nl -ba "$FILE"
        fi
    fi
}

# Summary: classes, functions, imports
view_summary() {
    case "$LANG" in
        python)
            echo "## Classes & Functions"
            grep -n "^class \|^def \|^async def " "$FILE" 2>/dev/null | head -50 || true
            echo ""
            echo "## Imports"
            grep -n "^import \|^from .* import" "$FILE" 2>/dev/null | head -20 || true
            ;;
        typescript|javascript)
            echo "## Exports & Classes"
            grep -n "^export \|^class \|^interface \|^type \|^function \|^const .* = (" "$FILE" 2>/dev/null | head -50 || true
            echo ""
            echo "## Imports"
            grep -n "^import " "$FILE" 2>/dev/null | head -20 || true
            ;;
        c|cpp)
            echo "## Classes & Functions"
            grep -n "^class \|^struct \|^enum \|^[a-zA-Z_].*(.*)[ ]*{$" "$FILE" 2>/dev/null | head -50 || true
            echo ""
            echo "## Includes"
            grep -n "^#include" "$FILE" 2>/dev/null | head -20 || true
            ;;
        java|kotlin)
            echo "## Classes & Methods"
            grep -n "^public \|^private \|^protected \|^class \|^interface " "$FILE" 2>/dev/null | head -50 || true
            echo ""
            echo "## Imports"
            grep -n "^import " "$FILE" 2>/dev/null | head -20 || true
            ;;
        go)
            echo "## Functions & Types"
            grep -n "^func \|^type " "$FILE" 2>/dev/null | head -50 || true
            echo ""
            echo "## Imports"
            sed -n '/^import/,/)/p' "$FILE" 2>/dev/null | head -20 || true
            ;;
        rust)
            echo "## Functions & Structs"
            grep -n "^pub \|^fn \|^struct \|^enum \|^impl " "$FILE" 2>/dev/null | head -50 || true
            echo ""
            echo "## Use statements"
            grep -n "^use " "$FILE" 2>/dev/null | head -20 || true
            ;;
        qml)
            echo "## Components & Properties"
            grep -n "^[A-Z][a-zA-Z]* {$\|^    [a-z]*:\|^    function \|^    signal " "$FILE" 2>/dev/null | head -50 || true
            ;;
        json)
            echo "## Top-level keys"
            if has_command jq; then
                jq -r 'keys[]' "$FILE" 2>/dev/null | head -30 || cat "$FILE" | grep -oE '"[^"]+":' | head -30
            else
                grep -oE '"[^"]+":' "$FILE" | sort -u | head -30
            fi
            ;;
        yaml)
            echo "## Top-level keys"
            grep -nE "^[a-zA-Z_]+" "$FILE" 2>/dev/null | head -30 || true
            ;;
        markdown)
            echo "## Headings"
            grep -nE "^#{1,4} " "$FILE" 2>/dev/null | head -30 || true
            ;;
        log)
            echo "## Log Summary"
            echo "Errors: $(grep -ciE "(error|fatal|critical)" "$FILE" 2>/dev/null || echo 0)"
            echo "Warnings: $(grep -ci "warn" "$FILE" 2>/dev/null || echo 0)"
            echo ""
            echo "## Recent errors:"
            grep -iE "(error|fatal|critical)" "$FILE" 2>/dev/null | tail -10 || true
            ;;
        bash)
            echo "## Functions"
            grep -n "^[a-zA-Z_][a-zA-Z0-9_]*() {" "$FILE" 2>/dev/null | head -50 || true
            echo ""
            echo "## Main logic"
            grep -n "^case \|^if \|^for \|^while " "$FILE" 2>/dev/null | head -20 || true
            ;;
        *)
            echo "## Structure"
            grep -nE "^[A-Z]|^\[|^#|^function |^def |^class " "$FILE" 2>/dev/null | head -50 || true
            ;;
    esac

    echo ""
    echo "[Summary: showed key structures from $TOTAL_LINES lines]"
}

# Preview: head + tail + structure
view_preview() {
    local preview_lines="${LINES:-10}"

    echo "## HEAD (first $preview_lines lines)"
    head -n "$preview_lines" "$FILE"

    if [[ $TOTAL_LINES -gt $((preview_lines * 3)) ]]; then
        echo ""
        echo "[... $((TOTAL_LINES - preview_lines * 2)) lines omitted ...]"
        echo ""
        echo "## TAIL (last $preview_lines lines)"
        tail -n "$preview_lines" "$FILE"
    fi

    echo ""
    echo "## STRUCTURE"
    view_structure

    local shown=$((preview_lines * 2 + 30))
    [[ $shown -gt $TOTAL_LINES ]] && shown=$TOTAL_LINES
    echo ""
    echo "[Preview: ~$shown of $TOTAL_LINES lines]"
}

# Structure only (uses shared pattern function)
view_structure() {
    case "$LANG" in
        json)
            if has_command jq; then
                jq -r 'paths | select(length == 1) | .[0]' "$FILE" 2>/dev/null | head -20 || true
            else
                grep -oE '"[^"]+":' "$FILE" | sort -u | head -20
            fi
            ;;
        *)
            local pattern
            pattern=$(get_structure_pattern "$LANG")
            grep -nE "$pattern" "$FILE" 2>/dev/null | head -30 || true
            ;;
    esac
}

# Special handlers for data formats
view_json() {
    if has_command jq; then
        if [[ $TOTAL_LINES -lt $SMALL_THRESHOLD ]]; then
            jq '.' "$FILE" 2>/dev/null || cat "$FILE"
        else
            echo "## Structure (large JSON - showing keys)"
            jq -r 'paths(scalars) | join(".")' "$FILE" 2>/dev/null | head -50 || true
            echo ""
            echo "## Sample (first 20 lines)"
            jq '.' "$FILE" 2>/dev/null | head -20 || head -20 "$FILE"
        fi
    else
        view_full
    fi
}

view_yaml() {
    YQ=$(find_yq)
    if [[ -n "$YQ" ]]; then
        if [[ $TOTAL_LINES -lt $SMALL_THRESHOLD ]]; then
            $YQ '.' "$FILE" 2>/dev/null || cat "$FILE"
        else
            echo "## Top-level structure"
            $YQ 'keys' "$FILE" 2>/dev/null | head -30 || grep -E "^[a-zA-Z]" "$FILE" | head -30
            echo ""
            echo "## Sample (first 30 lines)"
            head -30 "$FILE"
        fi
    else
        view_full
    fi
}

# Main dispatch
print_file_info

case "$LANG" in
    json)
        if [[ "$MODE" == "full" ]]; then
            view_json
        else
            view_summary
        fi
        ;;
    yaml)
        if [[ "$MODE" == "full" ]]; then
            view_yaml
        else
            view_summary
        fi
        ;;
    *)
        case "$MODE" in
            full) view_full ;;
            summary) view_summary ;;
            preview) view_preview ;;
            structure) view_structure ;;
        esac
        ;;
esac
